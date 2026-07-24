import SwiftUI
import UIKit

/// Le "témoin" : remplace la détection de vitesse de scroll par un levier
/// social plutôt que technique (voir docs/concept-produit.md section 5).
/// Aucun envoi automatique caché — Apple interdit d'envoyer un message sans
/// action explicite de l'utilisateur, et c'est très bien comme ça : le simple
/// fait de devoir choisir à qui l'envoyer fait déjà le travail.
enum AccountabilityMessage {
    static func text(overrideCount: Int) -> String {
        switch overrideCount {
        case 0:
            return "J'ai craqué et rouvert une app que j'essaie de limiter."
        case 1:
            return "Deuxième fois aujourd'hui que je craque sur une app que j'essaie de limiter."
        default:
            return "\(overrideCount + 1)e fois aujourd'hui que je craque sur une app que j'essaie de limiter."
        }
    }
}

/// Bouton qui ouvre le partage natif iOS (SMS, WhatsApp, etc.) avec un
/// message pré-rempli. L'utilisateur choisit le destinataire et appuie
/// lui-même sur envoyer, à chaque fois.
struct AccountabilityPromptButton: View {
    let overrideCount: Int
    @State private var isShareSheetPresented = false

    var body: some View {
        Button("Prévenir quelqu'un") {
            isShareSheetPresented = true
        }
        .sheet(isPresented: $isShareSheetPresented) {
            ActivityShareSheet(text: AccountabilityMessage.text(overrideCount: overrideCount))
        }
    }
}

private struct ActivityShareSheet: UIViewControllerRepresentable {
    let text: String

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [text], applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
