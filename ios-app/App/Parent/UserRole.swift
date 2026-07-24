import Foundation

/// Détermine si l'app s'auto-restreint (adulte) ou si un parent l'installe
/// sur l'appareil de son enfant. Ce choix change le type d'autorisation
/// Screen Time demandée (voir ScreenTimeAuthorization.swift) : c'est la
/// différence entre "je me fais confiance pour ne pas désinstaller l'app"
/// et "seul le code Temps d'écran du parent peut défaire les restrictions".
enum UserRole: String, Codable {
    case myself
    case child

    private static let key = "userRole"

    static func load() -> UserRole? {
        guard let raw = UserDefaults.shared.string(forKey: key) else { return nil }
        return UserRole(rawValue: raw)
    }

    func save() {
        UserDefaults.shared.set(rawValue, forKey: UserRole.key)
    }

    static var hasBeenSet: Bool { load() != nil }
}
