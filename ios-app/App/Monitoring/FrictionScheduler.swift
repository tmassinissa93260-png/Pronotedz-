import DeviceActivity
import FamilyControls
import Foundation

extension DeviceActivityName {
    static let dailyMonitoring = Self("dailyMonitoring")
}

extension DeviceActivityEvent.Name {
    static let sessionBudgetReached = Self("sessionBudgetReached")
}

/// Programme la surveillance quotidienne des apps choisies et déclenche
/// un événement quand le budget de session (10 min, voir AppConstants) est atteint.
/// La réaction à cet événement (appliquer le shield) est gérée côté
/// DeviceActivityMonitorExtension, dans un process séparé — c'est Apple qui
/// exécute ce code, pas l'app elle-même, même fermée.
enum FrictionScheduler {
    static func startMonitoring(selection: FamilyActivitySelection) {
        let center = DeviceActivityCenter()

        let schedule = DeviceActivitySchedule(
            intervalStart: DateComponents(hour: 0, minute: 0),
            intervalEnd: DateComponents(hour: 23, minute: 59),
            repeats: true
        )

        let event = DeviceActivityEvent(
            applications: selection.applicationTokens,
            categories: selection.categoryTokens,
            threshold: DateComponents(second: Int(AppConstants.sessionBudget))
        )

        do {
            try center.startMonitoring(
                .dailyMonitoring,
                during: schedule,
                events: [.sessionBudgetReached: event]
            )
        } catch {
            print("Impossible de démarrer la surveillance DeviceActivity : \(error)")
        }
    }

    static func stopMonitoring() {
        DeviceActivityCenter().stopMonitoring([.dailyMonitoring])
    }
}
