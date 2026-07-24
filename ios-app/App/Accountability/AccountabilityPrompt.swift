import SwiftUI
import UIKit
import MessageUI

/// Le "témoin" : remplace la détection de vitesse de scroll par un levier
/// social plutôt que technique (voir docs/concept-produit.md section 5).
/// Aucun envoi automatique caché — Apple interdit d'envoyer un message sans
/// action explicite de l'utilisateur, et c'est très bien comme ça : le simple
/// fait de devoir choisir à qui l'envoyer fait déjà le travail.
///
/// Deux comportements selon le profil (voir Parent/UserRole.swift) :
/// - Profil adulte : partage natif générique, l'utilisateur choisit le
///   destinataire à chaque fois (SMS, WhatsApp, peu importe).
/// - Profil enfant : le destinataire est fixé une fois pour toutes sur le
///   numéro du parent (ParentSettings), via le composeur SMS natif qui
///   permet de pré-remplir un destinataire précis — un enfant ne choisit
///   pas à qui il "doit rendre des comptes".
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

struct AccountabilityPromptButton: View {
    let overrideCount: Int
    @State private var isPresented = false

    private var role: UserRole { UserRole.load() ?? .myself }

    var body: some View {
        Button {
            isPresented = true
        } label: {
            Label("Prévenir quelqu'un", systemImage: "person.crop.circle.badge.exclamationmark")
                .font(.footnote.weight(.medium))
        }
        .buttonStyle(.bordered)
        .tint(.secondary)
        .sheet(isPresented: $isPresented) {
            if role == .child {
                ParentMessageComposer(
                    recipient: ParentSettings.load().parentPhoneNumber,
                    text: AccountabilityMessage.text(overrideCount: overrideCount)
                )
            } else {
                ActivityShareSheet(text: AccountabilityMessage.text(overrideCount: overrideCount))
            }
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

/// Composeur SMS avec destinataire pré-rempli (contrairement au partage
/// générique, MFMessageComposeViewController permet de fixer `.recipients`).
/// L'utilisateur doit tout de même appuyer sur envoyer lui-même — Apple ne
/// permet à aucune app tierce d'envoyer un SMS silencieusement.
private struct ParentMessageComposer: UIViewControllerRepresentable {
    let recipient: String
    let text: String

    func makeUIViewController(context: Context) -> UIViewController {
        guard MFMessageComposeViewController.canSendText() else {
            // Appareil sans capacité SMS (ex. iPad Wi-Fi seul) : repli simple.
            return UIHostingController(rootView: Text("Envoi de SMS indisponible sur cet appareil."))
        }
        let composer = MFMessageComposeViewController()
        composer.recipients = [recipient]
        composer.body = text
        composer.messageComposeDelegate = context.coordinator
        return composer
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MFMessageComposeViewControllerDelegate {
        func messageComposeViewController(
            _ controller: MFMessageComposeViewController,
            didFinishWith result: MessageComposeResult
        ) {
            controller.dismiss(animated: true)
        }
    }
}
