/// URI A2UI contract, renderer side (docs/a2ui/A2UI_ARCHITECTURE.md).
///
/// Mirrors `uri_a2ui/catalog.py`, `actions.py` and `validate.py`: the same
/// catalog, limits, action names and error codes. Both sides are checked
/// against `tests/a2ui/fixtures/contract_cases.json`. Every definition that
/// reaches the renderer is untrusted until [validateMessage] accepts it;
/// nothing is rendered from a refused message.
library;

const a2uiCatalogId = 'uri:a2ui/catalog/v1';
const a2uiVersion = 'v0.9';
const a2uiMaxComponents = 120;
const a2uiMaxDepth = 8;
const a2uiMaxString = 4000;
const a2uiMaxOptions = 80;
const a2uiMaxContextKeys = 16;
const a2uiMaxDataBytes = 64 * 1024;
const a2uiMaxContextString = 500;
const a2uiPlacements = ['companion', 'workspace', 'inline'];
const a2uiReadOnlyPrefixes = ['/bound'];

final _id = RegExp(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$');
final _surfaceId = RegExp(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$');
final _sha = RegExp(r'^[0-9a-f]{64}$');
final _segment = RegExp(r'^(?:[^~/]|~[01])*$');
final _urlish = RegExp(
  r'\b(?:https?|ftp|file)://|\b(?:javascript|vbscript|data):\S',
  caseSensitive: false,
);

const a2uiThemeKeys = {
  'agentDisplayName': 'text',
  'placement': 'enum:companion|workspace|inline',
};

const a2uiComponents = <String, Map<String, String>>{
  'Column': {'children': 'refs', 'gap': 'enum:none|small|medium|large'},
  'Row': {
    'children': 'refs',
    'gap': 'enum:none|small|medium|large',
    'align': 'enum:start|center|end|spaceBetween',
  },
  'Card': {'child': 'ref', 'tone': 'enum:neutral|accent|warning|danger'},
  'Text': {'text': 'text', 'variant': 'enum:title|body|caption|label'},
  'Divider': {},
  'Badge': {
    'text': 'text',
    'tone': 'enum:neutral|accent|success|warning|danger',
  },
  'Button': {
    'label': 'text',
    'action': 'action',
    'variant': 'enum:primary|secondary|danger',
    'enabled': 'bool',
  },
  'CheckBox': {'label': 'text', 'value': 'path'},
  'ChoicePicker': {
    'label': 'text',
    'value': 'path',
    'options': 'options',
    'multiple': 'bool',
  },
  'DateTimeInput': {'label': 'text', 'value': 'path', 'mode': 'enum:date|time'},
  'TextField': {
    'label': 'text',
    'value': 'path',
    'maxLength': 'int',
    'multiline': 'bool',
  },
  'ArtifactImage': {'artifactId': 'int', 'sha256': 'sha256', 'caption': 'text'},
  'List': {'children': 'refs'},
};

const a2uiRequired = <String, List<String>>{
  'Text': ['text'],
  'Badge': ['text'],
  'Button': ['label', 'action'],
  'CheckBox': ['label', 'value'],
  'ChoicePicker': ['label', 'value', 'options'],
  'DateTimeInput': ['label', 'value', 'mode'],
  'TextField': ['label', 'value'],
  'ArtifactImage': ['artifactId', 'sha256'],
  'Card': ['child'],
  'Column': ['children'],
  'Row': ['children'],
  'List': ['children'],
};

/// Registered action names and their context schemas (`uri_a2ui/actions.py`).
const a2uiActions = <String, Map<String, String>>{
  'scheduler.revise_proposal': {
    'selection': 'keys',
    'time': 'time',
    'offset_days': 'enum:1|2|3|5|7',
  },
  'scheduler.confirm_proposal': {
    'proposal_sha256': 'sha256',
    'selection': 'keys',
    'time': 'time',
    'offset_days': 'enum:1|2|3|5|7',
  },
  'scheduler.discard_proposal': {},
  'scheduler.review_artifact': {
    'artifact_sha256': 'sha256',
    'decision': 'enum:approve|regenerate|reject',
  },
  'scheduler.refine_artifact': {
    'artifact_sha256': 'sha256',
    'instruction': 'str',
  },
  'calendar.correct_record': {
    'record': 'str',
    'start': 'date?',
    'note': 'str?',
    'correction': 'enum:set_date|dispute|accept',
  },
  // URI Office (authority: uri_office service; bound change SHA-256, target re-read before writing).
  'office.apply_change': {'change_sha256': 'sha256'},
  'office.reject_change': {'change_sha256': 'sha256'},
  // URI Office O2 (authority: uri_office service; bound plan SHA-256; apply only queues the run).
  'office.run_plan': {'plan_sha256': 'sha256'},
  'office.discard_plan': {'plan_sha256': 'sha256'},
  'surface.dismiss': {},
};

class A2uiError {
  const A2uiError(this.code, this.path, [this.message = '']);
  final String code;
  final String path;
  final String message;
  @override
  String toString() => '$code@$path${message.isEmpty ? '' : ' ($message)'}';
}

/// An unpaired UTF-16 surrogate (mirrors Python `lone_surrogate`): refused as
/// text everywhere, so both sides size and store strings identically.
bool hasLoneSurrogate(String s) {
  for (var i = 0; i < s.length; i++) {
    final c = s.codeUnitAt(i);
    if (c >= 0xD800 && c <= 0xDBFF) {
      if (i + 1 < s.length) {
        final d = s.codeUnitAt(i + 1);
        if (d >= 0xDC00 && d <= 0xDFFF) {
          i++;
          continue;
        }
      }
      return true;
    }
    if (c >= 0xDC00 && c <= 0xDFFF) return true;
  }
  return false;
}

bool isPointer(Object? p, {bool relativeOk = true}) {
  if (p is! String || p.length > 256 || hasLoneSurrogate(p)) return false;
  if (p == '/') return true;
  String body;
  if (p.startsWith('/')) {
    body = p.substring(1);
  } else if (relativeOk && p.isNotEmpty) {
    body = p;
  } else {
    return false;
  }
  return body.split('/').every((s) => s.isNotEmpty && _segment.hasMatch(s));
}

bool isBinding(Object? v) =>
    v is Map && v.length == 1 && v.containsKey('path') && isPointer(v['path']);

bool _textOk(Object? s) =>
    s is String &&
    s.length <= a2uiMaxString &&
    !s.contains('\u0000') &&
    !hasLoneSurrogate(s);

bool _isInt(Object? v) => v is int;

List<A2uiError> checkValue(
  String kind,
  Object? v,
  String path, [
  Set<String>? allowedActions,
]) {
  A2uiError e(String c, [String m = '']) => A2uiError(c, path, m);
  if (kind == 'text') {
    return isBinding(v) || _textOk(v) ? [] : [e('BAD_TEXT')];
  }
  if (kind == 'bool') return v is bool || isBinding(v) ? [] : [e('BAD_BOOL')];
  if (kind == 'int') {
    return _isInt(v) && (v as int) >= 0 && v <= 1000000000
        ? []
        : [e('BAD_INT')];
  }
  if (kind == 'sha256') {
    return v is String && _sha.hasMatch(v) ? [] : [e('BAD_SHA256')];
  }
  if (kind.startsWith('enum:')) {
    return kind.substring(5).split('|').contains(v)
        ? []
        : [e('BAD_ENUM', 'allowed: ${kind.substring(5)}')];
  }
  if (kind == 'ref') {
    return v is String && _id.hasMatch(v) ? [] : [e('BAD_REF')];
  }
  if (kind == 'refs') {
    if (v is List) {
      if (v.length > a2uiMaxComponents ||
          !v.every((x) => x is String && _id.hasMatch(x))) {
        return [e('BAD_REFS')];
      }
      return [];
    }
    if (v is Map &&
        v.length == 2 &&
        v['componentId'] is String &&
        _id.hasMatch(v['componentId'] as String) &&
        isPointer(v['path'], relativeOk: false)) {
      return [];
    }
    return [e('BAD_REFS')];
  }
  if (kind == 'path') {
    if (!isBinding(v)) return [e('BAD_PATH')];
    final p = (v as Map)['path'] as String;
    if (a2uiReadOnlyPrefixes.any((pre) => p == pre || p.startsWith('$pre/'))) {
      return [e('READ_ONLY_PATH', 'inputs cannot write bound data')];
    }
    return [];
  }
  if (kind == 'options') {
    if (v is! List || v.isEmpty || v.length > a2uiMaxOptions) {
      return [e('BAD_OPTIONS')];
    }
    final errs = <A2uiError>[];
    for (var i = 0; i < v.length; i++) {
      final o = v[i];
      final ok =
          o is Map &&
          o.length == 2 &&
          o.containsKey('label') &&
          _textOk(o['label']) &&
          o['value'] is String &&
          (o['value'] as String).isNotEmpty &&
          (o['value'] as String).length <= 128 &&
          !hasLoneSurrogate(o['value'] as String);
      if (!ok) errs.add(A2uiError('BAD_OPTION', '$path/$i'));
    }
    final values = v.whereType<Map>().map((o) => o['value']).toSet();
    if (values.length != v.length) errs.add(e('DUPLICATE_OPTION'));
    return errs;
  }
  if (kind == 'action') return _checkActionDecl(v, path, allowedActions);
  return [e('UNKNOWN_KIND', kind)];
}

List<A2uiError> _checkActionDecl(Object? v, String path, Set<String>? allowed) {
  final ev = v is Map && v.length == 1 ? v['event'] : null;
  if (ev is! Map ||
      !ev.containsKey('name') ||
      ev.keys.any((k) => k != 'name' && k != 'context')) {
    return [
      A2uiError('BAD_ACTION', path, 'only {event: {name, context}} is allowed'),
    ];
  }
  final name = ev['name'];
  final ctx = ev['context'] ?? <String, dynamic>{};
  if (name is! String || !a2uiActions.containsKey(name)) {
    return [A2uiError('UNKNOWN_ACTION', path)];
  }
  if (allowed != null && !allowed.contains(name)) {
    return [A2uiError('ACTION_NOT_ALLOWED_ON_SURFACE', path, name)];
  }
  if (ctx is! Map || ctx.length > a2uiMaxContextKeys) {
    return [A2uiError('BAD_CONTEXT', path)];
  }
  final schema = a2uiActions[name]!;
  final errs = <A2uiError>[];
  ctx.forEach((k, val) {
    if (!schema.containsKey(k)) {
      errs.add(A2uiError('UNKNOWN_CONTEXT_KEY', '$path/event/context/$k'));
    } else if (!(isBinding(val) || _literalOk(val))) {
      errs.add(A2uiError('BAD_CONTEXT_VALUE', '$path/event/context/$k'));
    }
  });
  schema.forEach((k, kind) {
    if (!ctx.containsKey(k) && !kind.endsWith('?')) {
      errs.add(A2uiError('MISSING_CONTEXT_KEY', '$path/event/context/$k'));
    }
  });
  return errs;
}

bool _literalOk(Object? v) {
  if (v == null || v is bool) return true;
  if (v is int) return v >= 0 && v <= 1000000000;
  if (v is String) {
    return v.length <= a2uiMaxContextString && !hasLoneSurrogate(v);
  }
  if (v is List) {
    return v.length <= a2uiMaxOptions &&
        v.every((x) => x is String && x.length <= 128 && !hasLoneSurrogate(x));
  }
  return false;
}

void _noUrls(Object? obj, String path, List<A2uiError> errs) {
  if (obj is String) {
    if (_urlish.hasMatch(obj)) errs.add(A2uiError('URL_REFUSED', path));
  } else if (obj is Map) {
    obj.forEach((k, v) => _noUrls(v, '$path/$k', errs));
  } else if (obj is List) {
    for (var i = 0; i < obj.length; i++) {
      _noUrls(obj[i], '$path/$i', errs);
    }
  }
}

List<A2uiError> validateComponents(
  Object? components, [
  Set<String>? allowedActions,
  String path = '/components',
]) {
  final errs = <A2uiError>[];
  if (components is! List || components.isEmpty) {
    return [A2uiError('BAD_COMPONENTS', path)];
  }
  if (components.length > a2uiMaxComponents) {
    return [A2uiError('TOO_MANY_COMPONENTS', path, '${components.length}')];
  }
  final byId = <String, Map>{};
  final edges = <String, List<String>>{};
  for (var i = 0; i < components.length; i++) {
    final p = '$path/$i';
    final comp = components[i];
    if (comp is! Map ||
        !comp.containsKey('id') ||
        !comp.containsKey('component')) {
      errs.add(A2uiError('BAD_COMPONENT', p));
      continue;
    }
    final cid = comp['id'];
    final type = comp['component'];
    if (cid is! String || !_id.hasMatch(cid)) {
      errs.add(A2uiError('BAD_ID', p));
      continue;
    }
    if (byId.containsKey(cid)) {
      errs.add(A2uiError('DUPLICATE_ID', p, cid));
      continue;
    }
    if (type is! String || !a2uiComponents.containsKey(type)) {
      errs.add(A2uiError('UNKNOWN_COMPONENT', p));
      continue;
    }
    final spec = a2uiComponents[type]!;
    comp.forEach((k, v) {
      if (k == 'id' || k == 'component') return;
      if (!spec.containsKey(k)) {
        errs.add(A2uiError('UNKNOWN_PROPERTY', '$p/$k', '$type.$k'));
        return;
      }
      errs.addAll(checkValue(spec[k]!, v, '$p/$k', allowedActions));
    });
    for (final k in a2uiRequired[type] ?? const <String>[]) {
      if (!comp.containsKey(k)) {
        errs.add(A2uiError('MISSING_PROPERTY', '$p/$k', '$type.$k'));
      }
    }
    byId[cid] = comp;
    final kids = <String>[];
    if (comp['child'] is String) kids.add(comp['child'] as String);
    final ch = comp['children'];
    if (ch is List) {
      kids.addAll(ch.whereType<String>());
    } else if (ch is Map && ch['componentId'] is String) {
      kids.add(ch['componentId'] as String);
    }
    edges[cid] = kids;
  }
  _noUrls(components, path, errs);
  if (errs.isNotEmpty) return errs;
  if (!byId.containsKey('root')) return [A2uiError('NO_ROOT', path)];
  final parents = <String, String>{};
  edges.forEach((cid, kids) {
    for (final k in kids) {
      if (!byId.containsKey(k)) {
        errs.add(A2uiError('DANGLING_REF', path, '$cid -> $k'));
      } else if (parents.containsKey(k) || k == 'root') {
        errs.add(A2uiError('SHARED_OR_ROOT_CHILD', path, k));
      } else {
        parents[k] = cid;
      }
    }
  });
  if (errs.isNotEmpty) return errs;
  final seen = <String>{};
  final depthErr = <A2uiError>[];
  void walk(String cid, int depth, Set<String> stack) {
    if (stack.contains(cid)) {
      depthErr.add(A2uiError('CYCLE', path, cid));
      return;
    }
    if (depth > a2uiMaxDepth) {
      depthErr.add(A2uiError('TOO_DEEP', path, cid));
      return;
    }
    seen.add(cid);
    for (final k in edges[cid] ?? const <String>[]) {
      walk(k, depth + 1, {...stack, cid});
    }
  }

  walk('root', 1, {});
  errs.addAll(depthErr);
  final unreachable = byId.keys.where((k) => !seen.contains(k)).toList()
    ..sort();
  if (unreachable.isNotEmpty && depthErr.isEmpty) {
    errs.add(A2uiError('UNREACHABLE', path, unreachable.take(5).join(',')));
  }
  return errs;
}

int _utf8Length(String s) {
  var n = 0;
  for (final r in s.runes) {
    n += r < 0x80 ? 1 : (r < 0x800 ? 2 : (r < 0x10000 ? 3 : 4));
  }
  return n;
}

List<A2uiError> validateData(Object? value, String path, String raw) {
  if (_utf8Length(raw) > a2uiMaxDataBytes) {
    return [A2uiError('DATA_TOO_LARGE', path)];
  }
  final errs = <A2uiError>[];
  void walk(Object? v, String p) {
    if (v is String && (v.length > a2uiMaxString || hasLoneSurrogate(v))) {
      errs.add(A2uiError('BAD_TEXT', p));
    } else if (v is Map) {
      v.forEach((k, x) {
        if (k is! String || k.length > 256 || hasLoneSurrogate(k)) {
          errs.add(A2uiError('BAD_KEY', p));
        } else {
          walk(x, '$p/$k');
        }
      });
    } else if (v is List) {
      for (var i = 0; i < v.length; i++) {
        walk(v[i], '$p/$i');
      }
    }
  }

  walk(value, path);
  return errs;
}

const _messageKeys = [
  'createSurface',
  'updateComponents',
  'updateDataModel',
  'deleteSurface',
];
const _allowedFields = {
  'createSurface': {'surfaceId', 'catalogId', 'theme', 'sendDataModel'},
  'updateComponents': {'surfaceId', 'components'},
  'updateDataModel': {'surfaceId', 'path', 'value'},
  'deleteSurface': {'surfaceId'},
};

/// Errors for one server->client message (empty = valid). [encode] must be
/// the JSON encoder used for size checks (`jsonEncode`).
const a2uiMaxNesting = 32;

/// Iterative depth check before any recursive inspection (mirrors Python
/// `_nesting_ok`): hostile nesting is refused, never a stack overflow.
bool nestingOk(Object? obj, [int limit = a2uiMaxNesting]) {
  final stack = <(Object?, int)>[(obj, 1)];
  var seen = 0;
  while (stack.isNotEmpty) {
    final (v, d) = stack.removeLast();
    if (d > limit) return false;
    if (++seen > 200000) return false;
    if (v is Map) {
      for (final x in v.values) {
        stack.add((x, d + 1));
      }
    } else if (v is List) {
      for (final x in v) {
        stack.add((x, d + 1));
      }
    }
  }
  return true;
}

List<A2uiError> validateMessage(
  Object? msg,
  String Function(Object?) encode, [
  Set<String>? allowedActions,
]) {
  if (!nestingOk(msg)) {
    return [
      const A2uiError('TOO_NESTED', '/', 'more than $a2uiMaxNesting levels'),
    ];
  }
  if (msg is! Map || msg['version'] != a2uiVersion) {
    return [A2uiError('BAD_VERSION', '/version', 'expected $a2uiVersion')];
  }
  final keys = msg.keys.where((k) => k != 'version').toList();
  if (keys.length != 1 || !_messageKeys.contains(keys.first)) {
    return [const A2uiError('BAD_MESSAGE', '/')];
  }
  final kind = keys.first as String;
  final body = msg[kind];
  if (body is! Map ||
      body['surfaceId'] is! String ||
      !_surfaceId.hasMatch(body['surfaceId'] as String)) {
    return [A2uiError('BAD_SURFACE_ID', '/$kind/surfaceId')];
  }
  final extra = body.keys.where((k) => !_allowedFields[kind]!.contains(k));
  if (extra.isNotEmpty) return [A2uiError('UNKNOWN_FIELD', '/$kind')];
  if (kind == 'createSurface') {
    final errs = <A2uiError>[];
    if (body['catalogId'] != a2uiCatalogId) {
      errs.add(A2uiError('UNKNOWN_CATALOG', '/$kind/catalogId'));
    }
    final theme = body['theme'] ?? <String, dynamic>{};
    if (theme is! Map) {
      errs.add(A2uiError('BAD_THEME', '/$kind/theme'));
    } else {
      theme.forEach((k, v) {
        if (!a2uiThemeKeys.containsKey(k)) {
          errs.add(A2uiError('THEME_KEY_REFUSED', '/$kind/theme/$k'));
        } else {
          errs.addAll(checkValue(a2uiThemeKeys[k]!, v, '/$kind/theme/$k'));
        }
      });
    }
    if (body.containsKey('sendDataModel') && body['sendDataModel'] != false) {
      errs.add(A2uiError('SEND_DATA_MODEL_REFUSED', '/$kind/sendDataModel'));
    }
    return errs;
  }
  if (kind == 'updateComponents') {
    return validateComponents(
      body['components'],
      allowedActions,
      '/$kind/components',
    );
  }
  if (kind == 'updateDataModel') {
    final errs = <A2uiError>[];
    final p = body['path'] ?? '/';
    if (!isPointer(p, relativeOk: false)) {
      errs.add(A2uiError('BAD_PATH', '/$kind/path'));
    } else if (a2uiReadOnlyPrefixes.any(
      (pre) => p == pre || (p as String).startsWith('$pre/'),
    )) {
      // Bound data is set only by the authority's full model load (path "/").
      errs.add(A2uiError('READ_ONLY_PATH', '/$kind/path'));
    }
    if (body.containsKey('value')) {
      errs.addAll(
        validateData(body['value'], '/$kind/value', encode(body['value'])),
      );
    }
    return errs;
  }
  return [];
}

final _slug = RegExp(r'^[a-z][a-z0-9_]{0,63}$');
final _time = RegExp(r'^(?:[01]\d|2[0-3]):[0-5]\d$');
final _date = RegExp(r'^\d{4}-\d{2}-\d{2}$');

/// Renderer-side type check of one resolved context value (the authority
/// checks again; this only stops obviously wrong input before sending).
bool a2uiTyped(String kind, Object? v) {
  final opt = kind.endsWith('?');
  final k = opt ? kind.substring(0, kind.length - 1) : kind;
  if (v == null || v == '') return opt;
  if (v is String && hasLoneSurrogate(v)) return false;
  if (v is List && v.any((x) => x is String && hasLoneSurrogate(x))) {
    return false;
  }
  return switch (k) {
    'str' => v is String && v.length <= a2uiMaxContextString,
    'int' => v is int && v >= 0 && v <= 1000000,
    'bool' => v is bool,
    'sha256' => v is String && _sha.hasMatch(v),
    'time' => v is String && _time.hasMatch(v),
    'date' => v is String && _date.hasMatch(v),
    'keys' =>
      v is List &&
          v.length <= a2uiMaxOptions &&
          v.every((x) => x is String && _slug.hasMatch(x)),
    _ => k.startsWith('enum:') && k.substring(5).split('|').contains(v),
  };
}
