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
    @State private var step: Step = Self.initialStep()

    enum Step {
        case roleSelection
        case parentSetup
        case onboarding
        case appSelection
        case dashboard
        case waiting(duration: TimeInterval)
        case dailyLimitReached
        case redirect
    }

    private static func initialStep() -> Step {
        guard let role = UserRole.load() else { return .roleSelection }
        if role == .child, ParentSettings.load().parentPhoneNumber.isEmpty { return .parentSetup }
        guard InterestProfile.hasCompletedOnboarding else { return .onboarding }
        guard AppSelectionPicker.hasSavedSelection else { return .appSelection }
        if SessionState.hasReachedDailyCapToday { return .dailyLimitReached }
        return .dashboard
    }

    /// Choix entre .waiting et .dailyLimitReached selon que le plafond du
    /// jour (ParentSettings.dailyLimitMinutes) a été atteint ou non — à
    /// appeler depuis le vrai routage une fois câblé (voir note ci-dessous).
    private static func nextStepAfterShieldTriggered(duration: TimeInterval) -> Step {
        SessionState.hasReachedDailyCapToday ? .dailyLimitReached : .waiting(duration: duration)
    }

    static func handleIncomingURL(_ url: URL) {
        // Le routage réel (afficher WaitingScreenView/DailyLimitReachedView
        // au bon moment, via nextStepAfterShieldTriggered) doit passer par un
        // état partagé observable (ex. un ObservableObject injecté en
        // @EnvironmentObject) plutôt que cette fonction statique — simplifié
        // ici pour rester lisible dans ce squelette.
    }

    var body: some View {
        Group {
            switch step {
            case .roleSelection:
                RoleSelectionView { role in
                    role.save()
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = role == .child ? .parentSetup : .onboarding
                    }
                }
            case .parentSetup:
                ParentSetupView {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .onboarding
                    }
                }
            case .onboarding:
                OnboardingQuestionnaire {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .appSelection
                    }
                }
            case .appSelection:
                AppSelectionPicker {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .dashboard
                    }
                }
                .task { await authorization.requestAuthorization(for: UserRole.load() ?? .myself) }
            case .dashboard:
                DashboardView {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .appSelection
                    }
                }
            case .waiting(let duration):
                WaitingScreenView(totalWait: duration) {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .redirect
                    }
                }
            case .dailyLimitReached:
                DailyLimitReachedView {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .redirect
                    }
                }
            case .redirect:
                RedirectSuggestionView(
                    suggestions: SuggestionCatalog.pick(for: InterestProfile.load())
                ) {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        step = .dashboard
                    }
                }
            }
        }
        .transition(.opacity.combined(with: .scale(scale: 0.98)))
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: stepIdentity)
    }

    /// Valeur simple pour piloter l'animation de transition entre étapes
    /// (Step n'est pas Equatable à cause du TimeInterval associé).
    private var stepIdentity: Int {
        switch step {
        case .roleSelection: return 0
        case .parentSetup: return 1
        case .onboarding: return 2
        case .appSelection: return 3
        case .dashboard: return 4
        case .waiting: return 5
        case .dailyLimitReached: return 6
        case .redirect: return 7
        }
    }
}
