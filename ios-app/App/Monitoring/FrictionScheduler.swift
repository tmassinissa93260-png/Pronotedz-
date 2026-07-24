import DeviceActivity
import FamilyControls
import Foundation

extension DeviceActivityName {
    static let dailyMonitoring = Self("dailyMonitoring")
}

/// Programme la surveillance quotidienne des apps choisies : un événement par
/// palier décroissant de SessionBudgetPlan, plafonné au total réglé par le
/// parent (ParentSettings.dailyLimitMinutes + extraMinutesGrantedToday). Le
/// dernier événement ("dailyCap") marque le plafond dur du jour — voir
/// DeviceActivityMonitorExtension pour ce qui se passe quand il se déclenche.
///
/// Incertitude à vérifier en priorité dans Xcode : est-ce que ré-appeler
/// `startMonitoring` en cours de journée (`grantExtraTime`) repart bien du
/// temps déjà écoulé aujourd'hui pour les apps surveillées, ou recompte à
/// zéro ? Toute la mécanique "demander plus de temps" dépend de ce point,
/// non vérifiable sans compilateur/simulateur disponible ici.
enum FrictionScheduler {
    static func startMonitoring(selection: FamilyActivitySelection) {
        register(selection: selection)
    }

    /// Appelé une fois qu'une demande a été approuvée par le parent
    /// (voir TimeRequestSync.swift) : relève le plafond du jour et
    /// reprogramme la surveillance avec le nouveau seuil.
    static func grantExtraTime(minutes: Int) {
        guard
            let data = UserDefaults.shared.data(forKey: "monitoredSelection"),
            let selection = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data)
        else { return }

        var settings = ParentSettings.load()
        settings.grantExtraMinutes(minutes)
        register(selection: selection)
    }

    private static func register(selection: FamilyActivitySelection) {
        let center = DeviceActivityCenter()

        let schedule = DeviceActivitySchedule(
            intervalStart: DateComponents(hour: 0, minute: 0),
            intervalEnd: DateComponents(hour: 23, minute: 59),
            repeats: true
        )

        let settings = ParentSettings.load()
        let capMinutes = settings.dailyLimitMinutes + settings.extraMinutesGrantedToday
        let thresholds = SessionBudgetPlan.cumulativeThresholdsInSeconds(cappedAtMinutes: capMinutes)

        var events: [DeviceActivityEvent.Name: DeviceActivityEvent] = [:]
        for (index, cumulativeSeconds) in thresholds.enumerated() {
            let isCap = index == thresholds.count - 1
            let name = DeviceActivityEvent.Name(SessionBudgetPlan.eventName(forStepIndex: index, isCap: isCap))
            events[name] = DeviceActivityEvent(
                applications: selection.applicationTokens,
                categories: selection.categoryTokens,
                threshold: DateComponents(second: cumulativeSeconds)
            )
        }

        do {
            try center.startMonitoring(.dailyMonitoring, during: schedule, events: events)
        } catch {
            print("Impossible de démarrer/mettre à jour la surveillance DeviceActivity : \(error)")
        }
    }

    static func stopMonitoring() {
        DeviceActivityCenter().stopMonitoring([.dailyMonitoring])
    }

    /// À appeler après tout changement de `ParentSettings.dailyLimitMinutes`
    /// (voir ParentSettingsGateView) pour que le nouveau plafond s'applique
    /// tout de suite plutôt qu'au prochain redémarrage de la surveillance.
    static func reregisterIfPossible() {
        guard
            let data = UserDefaults.shared.data(forKey: "monitoredSelection"),
            let selection = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data)
        else { return }
        register(selection: selection)
    }
}
