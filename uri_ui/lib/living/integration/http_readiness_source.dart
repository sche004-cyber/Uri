import '../../services/app_state.dart';
import '../contracts/readiness_report.dart';
import '../widgets/status_badge.dart';

/// The HTTP shell cannot infer worker qualification or grants. Missing
/// adapter facts stay empty/not checked, never populated with mock readiness.
class HttpReadinessSource extends ReadinessSource {
  HttpReadinessSource(this.app) {
    app.addListener(notifyListeners);
  }
  final AppState app;
  @override
  bool get isSimulated => false;
  @override
  List<HarnessFact> get harnesses => const [];
  @override
  List<ClientFact> get clients => const [];
  @override
  List<PermissionFact> get permissions => const [];
  @override
  List<ReadinessCheck> get checks => [
    ReadinessCheck(
      id: 'brain',
      label: 'Brain selection',
      status: app.activeBrain == null
          ? TruthStatus.pending
          : TruthStatus.configured,
    ),
    const ReadinessCheck(
      id: 'worker',
      label: 'Worker qualification',
      status: TruthStatus.pending,
      detail: 'Not supplied by the HTTP client',
    ),
    const ReadinessCheck(
      id: 'grants',
      label: 'Runtime permission grants',
      status: TruthStatus.pending,
      detail: 'Review actual client capabilities in all settings',
    ),
  ];
  @override
  Future<void> refresh() async {
    await app.loadActiveBrain();
    notifyListeners();
  }

  @override
  void dispose() {
    app.removeListener(notifyListeners);
    super.dispose();
  }
}
