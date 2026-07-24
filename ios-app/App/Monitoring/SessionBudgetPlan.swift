import Foundation

/// Remplace la détection de vitesse de scroll (impossible sur iPhone, voir
/// docs/concept-produit.md section 5) : au lieu d'essayer de mesurer un
/// comportement pendant la session, on rend la durée d'accès elle-même
/// imprévisible et décroissante à chaque réouverture dans la journée.
/// Même ressort psychologique que le renforcement variable (l'incertitude),
/// tourné contre l'envie de revenir plutôt que pour.
enum SessionBudgetPlan {
    /// Paliers en minutes : généreux la première fois, puis de plus en plus
    /// courts jusqu'à un plancher de 2 min.
    static let stepMinutes: [Int] = [10, 5, 2, 2, 2, 2, 2, 2]

    /// Seuils cumulés en secondes, tels qu'attendus par DeviceActivityEvent
    /// (le framework ne connaît que du temps cumulé dans la journée, pas des
    /// sessions individuelles — voir FrictionScheduler).
    static var cumulativeThresholdsInSeconds: [Int] {
        var total = 0
        return stepMinutes.map { minutes in
            total += minutes * 60
            return total
        }
    }

    static func eventName(forStepIndex index: Int) -> String {
        "budgetStep\(index)"
    }
}
