import Foundation
import Observation

#if canImport(FoundationModels)
import FoundationModels

/// Coach IA basé sur le framework Foundation Models d'Apple (iOS 26+), qui
/// fait tourner un modèle de langage directement sur l'appareil — aucune
/// donnée envoyée à un serveur, cohérent avec un produit qui parle de
/// reprendre le contrôle sur ses écrans. Écrit sans Xcode/simulateur
/// disponible : les noms exacts d'API (notamment les cas de
/// `SystemLanguageModel.Availability`) sont reconstitués de mémoire et à
/// vérifier à la compilation.
///
/// Toute la classe est gatée iOS 26 plutôt que gérée en interne, pour éviter
/// un contournement fragile de type erasure : c'est à l'écran appelant
/// (voir CoachChatView) de vérifier `#available` et d'afficher un repli sur
/// les versions plus anciennes. Le coach n'est jamais un prérequis pour le
/// reste de l'app.
@available(iOS 26.0, *)
@Observable
final class CoachSession {
    private(set) var messages: [CoachMessage] = []
    private(set) var isResponding = false
    private(set) var unavailabilityReason: String?
    private var languageSession: LanguageModelSession?

    func start(interestProfile: InterestProfile, overridesToday: Int) {
        switch SystemLanguageModel.default.availability {
        case .available:
            languageSession = LanguageModelSession(
                instructions: Self.instructions(interestProfile: interestProfile, overridesToday: overridesToday)
            )
            unavailabilityReason = nil
            if messages.isEmpty {
                messages.append(CoachMessage(role: .coach, text: "Salut. De quoi tu as besoin là, tout de suite ?"))
            }
        case .unavailable:
            // Apple expose normalement un motif précis (device non éligible,
            // Apple Intelligence désactivé, modèle en cours de préparation) —
            // à récupérer et afficher plus finement une fois compilable.
            unavailabilityReason = "Apple Intelligence n'est pas activé ou pas encore prêt sur cet appareil."
        @unknown default:
            unavailabilityReason = "Coach IA indisponible pour une raison inconnue."
        }
    }

    func send(_ text: String) async {
        messages.append(CoachMessage(role: .user, text: text))
        isResponding = true
        defer { isResponding = false }

        guard let languageSession else {
            messages.append(CoachMessage(role: .coach, text: Self.fallbackReply()))
            return
        }
        do {
            let response = try await languageSession.respond(to: text)
            messages.append(CoachMessage(role: .coach, text: response.content))
        } catch {
            messages.append(CoachMessage(role: .coach, text: Self.fallbackReply()))
        }
    }

    private static func instructions(interestProfile: InterestProfile, overridesToday: Int) -> String {
        """
        Tu es un coach bienveillant qui aide une personne à réduire le scroll compulsif \
        sur les réseaux sociaux. Ton style : direct mais jamais culpabilisant, orienté \
        action concrète immédiate plutôt que discours général sur les dangers des écrans.
        Réponds en 2-3 phrases maximum.

        Contexte de cette conversation : aujourd'hui, cette personne a forcé l'accès à une \
        app qu'elle essaie de limiter \(overridesToday) fois. Ses centres d'intérêt \
        déclarés : \(interestProfile.tags.map(\.rawValue).joined(separator: ", ")).
        """
    }

    private static func fallbackReply() -> String {
        "Le coach n'est pas joignable là, mais voilà un rappel qui tient toujours : \(MessageBank.random().text)"
    }
}

#endif

struct CoachMessage: Identifiable {
    let id = UUID()
    let role: Role
    let text: String

    enum Role {
        case user
        case coach
    }
}
