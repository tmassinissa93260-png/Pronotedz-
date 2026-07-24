import Foundation

/// État de friction partagé entre l'app principale et les extensions,
/// stocké dans l'App Group pour être lisible depuis DeviceActivityMonitorExtension
/// et ShieldActionExtension.
struct SessionState {
    private static let lastSessionEndKey = "lastSessionEndDate"
    private static let overridesTodayKey = "overridesToday"
    private static let overridesDateKey = "overridesTodayDate"

    private static var defaults: UserDefaults { .shared }

    static var lastSessionEndDate: Date? {
        get { defaults.object(forKey: lastSessionEndKey) as? Date }
        set { defaults.set(newValue, forKey: lastSessionEndKey) }
    }

    /// Nombre de fois où l'utilisateur a forcé un nouvel accès aujourd'hui,
    /// remis à zéro automatiquement à chaque nouveau jour calendaire.
    static var overridesToday: Int {
        get {
            guard isOverrideCountFromToday else { return 0 }
            return defaults.integer(forKey: overridesTodayKey)
        }
        set {
            defaults.set(newValue, forKey: overridesTodayKey)
            defaults.set(Date(), forKey: overridesDateKey)
        }
    }

    private static var isOverrideCountFromToday: Bool {
        guard let storedDate = defaults.object(forKey: overridesDateKey) as? Date else {
            return false
        }
        return Calendar.current.isDateInToday(storedDate)
    }

    /// Durée d'attente à imposer avant d'accorder l'accès, en fonction de
    /// l'historique du jour : 30s pour le tout premier essai, 2 min ensuite.
    static func requiredWait(now: Date = Date()) -> TimeInterval {
        guard let lastEnd = lastSessionEndDate else {
            return AppConstants.firstAttemptWait
        }
        // Une session vient de se terminer récemment : c'est une tentative
        // de réouverture, pas un premier accès de la journée.
        let sinceEnd = now.timeIntervalSince(lastEnd)
        if sinceEnd < 60 * 60 {
            return AppConstants.cooldownWait
        }
        return AppConstants.firstAttemptWait
    }

    static func recordSessionEnd() {
        lastSessionEndDate = Date()
    }

    static func recordOverride() {
        overridesToday += 1
    }
}
