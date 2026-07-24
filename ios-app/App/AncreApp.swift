import SwiftUI

@main
struct AncreApp: App {
    @StateObject private var authorization = ScreenTimeAuthorization()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(authorization)
                // Reçoit l'ouverture déclenchée par ShieldActionExtension
                // (ancre://waiting) — voir README-SETUP.md pour l'URL Type
                // à déclarer dans Xcode.
                .onOpenURL { url in
                    RootView.handleIncomingURL(url)
                }
        }
    }
}

/// Assemble les écrans dans l'ordre du flux décrit dans
/// docs/concept-produit.md : onboarding (une fois) → sélection des apps
/// → écran d'attente → redirection.
struct RootView: View {
    @EnvironmentObject private var authorization: ScreenTimeAuthorization
    @State private var step: Step = InterestProfile.hasCompletedOnboarding ? .appSelection : .onboarding

    enum Step {
        case onboarding
        case appSelection
        case waiting(duration: TimeInterval)
        case redirect
    }

    static func handleIncomingURL(_ url: URL) {
        // Le routage réel (afficher WaitingScreenView avec la bonne durée)
        // doit passer par un état partagé observable (ex. un ObservableObject
        // injecté en @EnvironmentObject) plutôt que cette fonction statique —
        // simplifié ici pour rester lisible dans ce squelette.
    }

    var body: some View {
        Group {
            switch step {
            case .onboarding:
                OnboardingQuestionnaire {
                    step = .appSelection
                }
            case .appSelection:
                AppSelectionPicker()
                    .task { await authorization.requestAuthorization() }
            case .waiting(let duration):
                WaitingScreenView(totalWait: duration) {
                    step = .redirect
                }
            case .redirect:
                RedirectSuggestionView(
                    suggestions: SuggestionCatalog.pick(for: InterestProfile.load())
                ) {
                    // Échappatoire assumée : voir RedirectSuggestionView.
                }
            }
        }
    }
}
