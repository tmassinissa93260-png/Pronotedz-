import Foundation

/// Identifiants partagés entre l'app et les 4 extensions.
/// À remplacer par les vrais identifiants une fois le compte développeur configuré
/// (voir README-SETUP.md).
enum AppConstants {
    static let appGroupID = "group.com.ancre.app"
    static let urlScheme = "ancre"

    /// Attente avant le tout premier accès de la journée.
    static let firstAttemptWait: TimeInterval = 30

    /// Attente en cas de tentative de réouverture juste après une session terminée.
    static let cooldownWait: TimeInterval = 2 * 60
}

extension UserDefaults {
    static var shared: UserDefaults {
        UserDefaults(suiteName: AppConstants.appGroupID) ?? .standard
    }
}
