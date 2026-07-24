import Foundation

enum MessageTone {
    case direct
    case positive
}

struct WaitingMessage {
    let text: String
    let tone: MessageTone
}

/// Volontairement plus de messages positifs que directs (voir
/// docs/concept-produit.md section 6bis) : la culpabilisation seule augmente
/// le taux de désinstallation à moyen terme d'après la littérature sur le
/// changement de comportement.
enum MessageBank {
    static let messages: [WaitingMessage] = [
        WaitingMessage(text: "Il fait beau dehors, ça te dit une sortie rapide ?", tone: .positive),
        WaitingMessage(text: "Tu devrais être en train d'avancer sur ce que tu as prévu.", tone: .direct),
        WaitingMessage(text: "Un ballon qui prend la poussière, ça te dit quelque chose ?", tone: .positive),
        WaitingMessage(text: "Ce scroll ne t'apporte rien que tu ne saches déjà.", tone: .direct),
        WaitingMessage(text: "10 minutes de marche valent plus que 10 minutes de flux.", tone: .positive),
        WaitingMessage(text: "Ce n'est pas le contenu qui te retient, c'est l'incertitude du suivant.", tone: .direct)
    ]

    /// Pioche pondérée : ~70% de messages positifs, ~30% de messages directs.
    static func random() -> WaitingMessage {
        let positive = messages.filter { $0.tone == .positive }
        let direct = messages.filter { $0.tone == .direct }
        if Double.random(in: 0..<1) < 0.7, let pick = positive.randomElement() {
            return pick
        }
        return direct.randomElement() ?? messages[0]
    }
}
