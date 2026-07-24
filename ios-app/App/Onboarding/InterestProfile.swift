import Foundation

enum InterestTag: String, CaseIterable, Codable {
    case lecture
    case documentaire
    case sport
    case sortieAccompagne
    case sortieSeul
}

struct InterestProfile: Codable {
    var tags: Set<InterestTag>

    private static let key = "interestProfile"

    static func load() -> InterestProfile {
        guard
            let data = UserDefaults.shared.data(forKey: key),
            let profile = try? JSONDecoder().decode(InterestProfile.self, from: data)
        else {
            return InterestProfile(tags: [])
        }
        return profile
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else { return }
        UserDefaults.shared.set(data, forKey: InterestProfile.key)
    }

    static var hasCompletedOnboarding: Bool {
        UserDefaults.shared.data(forKey: key) != nil
    }
}
