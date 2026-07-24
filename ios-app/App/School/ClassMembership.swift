import Foundation

/// Rattachement (optionnel) d'un élève à une classe. Ne fait rien seul —
/// c'est SchoolSync.swift qui envoie réellement les chiffres vers CloudKit.
/// Le nom affiché est choisi par l'élève : garder à l'esprit qu'un vrai
/// déploiement en école devrait probablement préférer un pseudonyme/code
/// attribué par l'enseignant plutôt qu'un nom identifiant, pour limiter ce
/// qui circule sur des enfants — choix laissé de côté ici à la demande
/// explicite du produit (le prof voit le détail élève par élève).
struct ClassMembership: Codable {
    var classCode: String
    var displayName: String

    private static let key = "classMembership"

    static func load() -> ClassMembership? {
        guard
            let data = UserDefaults.shared.data(forKey: key),
            let membership = try? JSONDecoder().decode(ClassMembership.self, from: data)
        else { return nil }
        return membership
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else { return }
        UserDefaults.shared.set(data, forKey: ClassMembership.key)
    }

    static func clear() {
        UserDefaults.shared.removeObject(forKey: key)
    }
}
