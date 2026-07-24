import DeviceActivity
import FamilyControls
import Foundation

extension DeviceActivityName {
    static let dailyMonitoring = Self("dailyMonitoring")
}

/// Programme la surveillance quotidienne des apps choisies et déclenche un
/// événement à chaque palier de SessionBudgetPlan (10, 5, 2, 2... minutes
/// cumulées). La réaction à chaque palier (appliquer le shield) est gérée
/// côté DeviceActivityMonitorExtension, dans un process séparé — c'est Apple
/// qui exécute ce code, pas l'app elle-même, même fermée.
enum FrictionScheduler {
    static func startMonitoring(selection: FamilyActivitySelection) {
        let center = DeviceActivityCenter()

        let schedule = DeviceActivitySchedule(
            intervalStart: DateComponents(hour: 0, minute: 0),
            intervalEnd: DateComponents(hour: 23, minute: 59),
            repeats: true
        )

        var events: [DeviceActivityEvent.Name: DeviceActivityEvent] = [:]
        for (index, cumulativeSeconds) in SessionBudgetPlan.cumulativeThresholdsInSeconds.enumerated() {
            let name = DeviceActivityEvent.Name(SessionBudgetPlan.eventName(forStepIndex: index))
            events[name] = DeviceActivityEvent(
                applications: selection.applicationTokens,
                categories: selection.categoryTokens,
                threshold: DateComponents(second: cumulativeSeconds)
            )
        }

        do {
            try center.startMonitoring(.dailyMonitoring, during: schedule, events: events)
        } catch {
            print("Impossible de démarrer la surveillance DeviceActivity : \(error)")
        }
    }

    static func stopMonitoring() {
        DeviceActivityCenter().stopMonitoring([.dailyMonitoring])
    }
}
