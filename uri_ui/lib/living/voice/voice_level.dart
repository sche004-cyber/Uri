import 'dart:math' as math;
import 'dart:typed_data';

/// Turns raw audio loudness into the one display level the voice waveform
/// draws.
///
/// There is one mapping and it does not know who is speaking. The user's
/// microphone and URI's own speech each get an instance of this class with the
/// same constants, so equal audio produces an equal waveform and neither
/// speaker can be made to look more powerful than the other. Sources hand over
/// raw block RMS (linear, full scale = 1.0) and never pre-scale.
///
/// Why there is a slow reference level: a desktop microphone typically
/// delivers conversational speech around -30 dBFS while synthesised speech is
/// normalised near -20 dBFS. A fixed absolute mapping would therefore draw
/// URI larger than the user for the same speaking effort. Each stream instead
/// tracks its own typical speech level ([referenceDb]) with the same slow,
/// bounded follower, and the level is measured relative to it. Equivalent
/// speech on either stream draws the same waveform; the adaptation can never
/// exceed [maxGainDb] in either direction.
class VoiceLevelMapper {
  VoiceLevelMapper();

  /// Where the reference starts, and the centre of its permitted range.
  static const double nominalDb = -22;

  /// The reference may move this far either side of [nominalDb], so a dead
  /// or clipping input is shown as quiet or loud rather than normalised away.
  static const double maxGainDb = 10;

  /// Blocks below this are never speech, whatever the reference.
  static const double absoluteFloorDb = -60;

  /// The display range relative to the reference: [rangeBelowDb] under it is
  /// silence, [rangeAboveDb] over it is full.
  static const double rangeBelowDb = 26;
  static const double rangeAboveDb = 10;

  /// Rise and fall time constants. Fast attack keeps syllable onsets visible;
  /// the slower release stops the waves collapsing between words, which is
  /// what makes the motion read as fluid instead of jittery.
  static const double attackMs = 35;
  static const double releaseMs = 170;

  /// The slow follower behind [flux]: how far the level currently rises above
  /// its recent average, used to add ripple on onsets.
  static const double slowMs = 650;

  /// How quickly the reference follows the stream's typical speech level.
  static const double referenceMs = 2500;

  double _level = 0;
  double _slow = 0;
  double _ref = nominalDb;

  /// 0..1 smoothed display level.
  double get level => _level;

  /// 0..1 onset emphasis: the fast level minus the slow one, clamped.
  double get flux => (_level - _slow).clamp(0.0, 1.0);

  /// The stream's current typical speech level in dBFS.
  double get referenceDb => _ref;

  /// Starts a new turn from silence. The reference is kept: it describes the
  /// stream (this microphone, this voice), not the turn.
  void reset() {
    _level = 0;
    _slow = 0;
  }

  static double dbfs(double rms) =>
      rms <= 1e-9 ? -120.0 : 20.0 * math.log(rms) / math.ln10;

  /// The instantaneous target for one block, before smoothing, against a
  /// reference of [refDb].
  static double target(double rms, [double refDb = nominalDb]) {
    final db = dbfs(rms);
    if (db < absoluteFloorDb) return 0;
    final lo = refDb - rangeBelowDb;
    final x = ((db - lo) / (rangeBelowDb + rangeAboveDb)).clamp(0.0, 1.0);
    // Ease-in: quiet speech stays visible but small, and typical speech sits
    // near the middle, leaving the top of the range for emphasis.
    return math.pow(x, 1.6).toDouble();
  }

  /// Feeds one block of audio whose RMS is [rms], covering [blockMs].
  void addBlock(double rms, double blockMs) {
    final db = dbfs(rms);
    // Only blocks that are plausibly speech move the reference.
    if (db > _ref - 18 && db > absoluteFloorDb) {
      _ref += (db - _ref) * (1 - math.exp(-blockMs / referenceMs));
      _ref = _ref.clamp(nominalDb - maxGainDb, nominalDb + maxGainDb);
    }
    final goal = target(rms, _ref);
    final tau = goal > _level ? attackMs : releaseMs;
    _level += (goal - _level) * (1 - math.exp(-blockMs / tau));
    _slow += (_level - _slow) * (1 - math.exp(-blockMs / slowMs));
  }
}

/// One block of measured loudness from an audio stream.
class LevelFrame {
  const LevelFrame(this.tMs, this.rms);

  /// Offset of the block's start from the beginning of the stream.
  final int tMs;

  /// Linear RMS of the block, full scale 1.0.
  final double rms;
}

/// Linear RMS of 16-bit PCM samples in `[start, end)`.
double rmsPcm16(Int16List samples, [int start = 0, int? end]) {
  final stop = math.min(end ?? samples.length, samples.length);
  if (stop <= start) return 0;
  var acc = 0.0;
  for (var i = start; i < stop; i++) {
    final v = samples[i] / 32768.0;
    acc += v * v;
  }
  return math.sqrt(acc / (stop - start));
}

/// The loudness envelope of a PCM16 stream in fixed blocks. This is the same
/// computation a live capture or playback tap performs on each buffer it sees.
List<LevelFrame> levelEnvelope(
  Int16List samples,
  int sampleRate, {
  int blockMs = 20,
}) {
  final n = math.max(1, sampleRate * blockMs ~/ 1000);
  return <LevelFrame>[
    for (var s = 0; s < samples.length; s += n)
      LevelFrame(s * 1000 ~/ sampleRate, rmsPcm16(samples, s, s + n)),
  ];
}

/// Decoded mono PCM16 audio.
class PcmClip {
  const PcmClip(this.samples, this.sampleRate);
  final Int16List samples;
  final int sampleRate;

  int get durationMs => samples.length * 1000 ~/ sampleRate;
}

/// Minimal RIFF/WAVE reader for mono 16-bit PCM, the format the fixtures and
/// the existing voice adapter both use. Throws [FormatException] otherwise.
PcmClip decodeWavPcm16(Uint8List bytes) {
  final b = ByteData.sublistView(bytes);
  String tag(int o) => String.fromCharCodes(bytes.sublist(o, o + 4));
  if (bytes.length < 12 || tag(0) != 'RIFF' || tag(8) != 'WAVE') {
    throw const FormatException('not a RIFF/WAVE file');
  }
  var o = 12;
  int? rate;
  int? channels;
  int? bits;
  while (o + 8 <= bytes.length) {
    final id = tag(o);
    final size = b.getUint32(o + 4, Endian.little);
    final body = o + 8;
    if (id == 'fmt ') {
      final format = b.getUint16(body, Endian.little);
      channels = b.getUint16(body + 2, Endian.little);
      rate = b.getUint32(body + 4, Endian.little);
      bits = b.getUint16(body + 14, Endian.little);
      if (format != 1) throw FormatException('unsupported WAVE format $format');
    } else if (id == 'data') {
      if (rate == null || channels != 1 || bits != 16) {
        throw FormatException(
          'expected mono 16-bit PCM, got $channels ch / $bits bit',
        );
      }
      final len = math.min(size, bytes.length - body) ~/ 2;
      final out = Int16List(len);
      for (var i = 0; i < len; i++) {
        out[i] = b.getInt16(body + i * 2, Endian.little);
      }
      return PcmClip(out, rate);
    }
    o = body + size + (size.isOdd ? 1 : 0);
  }
  throw const FormatException('no data chunk');
}
