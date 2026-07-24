import DeviceActivity
import ManagedSettings
import FamilyControls
import Foundation

/// Tourne dans son propre process, géré par iOS, même si l'app principale est
/// fermée. C'est ici que le budget de 10 minutes (AppConstants.sessionBudget)
/// se traduit réellement en fermeture forcée de l'app surveillée.
class DeviceActivityMonitorExtension: DeviceActivityMonitor {
    private let store = ManagedSettingsStore()

    override func eventDidReachThreshold(
        _ event: DeviceActivityEvent.Name,
        activity: DeviceActivityName
    ) {
        super.eventDidReachThreshold(event, activity: activity)
        guard event == .sessionBudgetReached else { return }

        applyShieldToMonitoredSelection()
        SessionState.recordSessionEnd()
    }

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        // Nouvelle journée : on retire un éventuel shield de la veille.
        store.shield.applications = nil
        store.shield.applicationCategories = nil
    }

    private func applyShieldToMonitoredSelection() {
        guard
            let data = UserDefaults.shared.data(forKey: "monitoredSelection"),
            let selection = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data)
        else { return }

        store.shield.applications = selection.applicationTokens
        store.shield.applicationCategories = .specific(selection.categoryTokens)
    }
}
