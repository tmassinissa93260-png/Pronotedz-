import Foundation

/// Remplace la détection de vitesse de scroll (impossible sur iPhone, voir
/// docs/concept-produit.md section 5) : au lieu d'essayer de mesurer un
/// comportement pendant la session, on rend la durée d'accès elle-même
/// imprévisible et décroissante à chaque réouverture dans la journée —
/// jusqu'à un plafond quotidien réglable par le parent (ParentSettings).
enum SessionBudgetPlan {
    /// Paliers en minutes : généreux la première fois, puis de plus en plus
    /// courts. S'arrête dès que le cumul dépasse le plafond du jour.
    static let stepMinutes: [Int] = [10, 5, 2, 2, 2, 2, 2, 2, 2, 2]

    /// Seuils cumulés en secondes, plafonnés à `capMinutes` (le plafond
    /// quotidien + les minutes accordées en plus par le parent ce jour-là).
    /// Le dernier seuil de la liste correspond toujours au plafond dur —
    /// au-delà, plus aucune session n'est accordée sans demande approuvée.
    static func cumulativeThresholdsInSeconds(cappedAtMinutes capMinutes: Int) -> [Int] {
        var total = 0
        var thresholds: [Int] = []
        for minutes in stepMinutes {
            total += minutes * 60
            if total >= capMinutes * 60 { break }
            thresholds.append(total)
        }
        thresholds.append(capMinutes * 60)
        return thresholds
    }

    static func eventName(forStepIndex index: Int, isCap: Bool) -> String {
        isCap ? "dailyCap" : "budgetStep\(index)"
    }
}
