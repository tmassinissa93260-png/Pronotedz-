import Foundation

struct Suggestion {
    let title: String
    let description: String
    let tag: InterestTag
}

/// Catalogue statique volontairement simple pour le MVP : pas besoin d'API
/// externe pour proposer 2-3 alternatives crédibles (cf. concept-produit.md
/// section 6ter). À enrichir/rendre dynamique en V2 si besoin.
enum SuggestionCatalog {
    static let all: [Suggestion] = [
        Suggestion(title: "15 min d'un roman que tu as commencé", description: "Même une seule page suffit à casser l'automatisme.", tag: .lecture),
        Suggestion(title: "Un article de fond plutôt qu'un fil d'actu", description: "Une lecture longue, un seul sujet, pas de scroll.", tag: .lecture),
        Suggestion(title: "Un documentaire d'une vingtaine de minutes", description: "Un format court mais avec un vrai début et une vraie fin.", tag: .documentaire),
        Suggestion(title: "Un épisode de podcast", description: "Pour les mains libres, en marchant par exemple.", tag: .documentaire),
        Suggestion(title: "10 minutes de marche ou de course", description: "Le temps que durait la session que tu viens de terminer.", tag: .sport),
        Suggestion(title: "Un ballon, un mur, dix minutes", description: "Pas besoin d'un vrai match pour que ça compte.", tag: .sport),
        Suggestion(title: "Appeler ou passer voir quelqu'un", description: "Une vraie conversation plutôt que des contenus.", tag: .sortieAccompagne),
        Suggestion(title: "Une balade sans destination précise", description: "Sortir, sans autre objectif que sortir.", tag: .sortieSeul)
    ]

    /// Tire 2-3 suggestions parmi celles correspondant aux tags du profil,
    /// en évitant de répéter la dernière suggestion montrée.
    static func pick(for profile: InterestProfile, excluding lastShown: String? = nil, count: Int = 3) -> [Suggestion] {
        let matching = all.filter { profile.tags.contains($0.tag) && $0.title != lastShown }
        let pool = matching.isEmpty ? all : matching
        return Array(pool.shuffled().prefix(count))
    }
}
