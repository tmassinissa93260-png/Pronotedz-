import Foundation
import CryptoKit

/// Contact du parent (pour le "témoin", voir Accountability/) et réglages
/// propres au mode enfant, configurés une fois lors du setup.
///
/// Distinction importante à ne pas perdre de vue : le PIN ici (`settingsPIN`)
/// est une protection *applicative* pour éviter qu'un enfant change les
/// réglages en deux taps — ce n'est PAS ce qui empêche la désinstallation ou
/// la levée des restrictions Screen Time. Cette protection-là vient
/// uniquement de l'autorisation `.child` demandée à Apple (voir
/// ScreenTimeAuthorization.swift), gérée par le code Temps d'écran du
/// parent au niveau du système, hors de portée de notre code. Un enfant qui
/// réinitialise l'app efface ce PIN local — à ne jamais présenter comme une
/// protection réelle contre la suppression de l'app elle-même.
struct ParentSettings: Codable {
    var parentName: String
    var parentPhoneNumber: String
    var isCoachEnabledForChild: Bool

    /// Plafond quotidien total sur les apps surveillées (voir FrictionScheduler).
    /// Une fois atteint, plus aucune session n'est accordée sans passer par
    /// une demande approuvée par le parent (voir TimeRequestSync.swift).
    var dailyLimitMinutes: Int = 120

    /// Code court généré une fois, à communiquer au parent pour qu'il puisse
    /// suivre l'enfant depuis son propre téléphone (ParentRemoteView) — même
    /// logique que le code de classe côté école, voir School/ClassMembership.swift.
    var familyCode: String = ParentSettings.generateFamilyCode()

    /// Minutes accordées en plus du plafond aujourd'hui, remises à zéro
    /// chaque jour (voir `resetDailyStateIfNeeded`).
    var extraMinutesGrantedToday: Int = 0
    private var extraMinutesGrantedDate: String? = nil

    private var pinHash: String? = nil

    private static let key = "parentSettings"

    static func load() -> ParentSettings {
        guard
            let data = UserDefaults.shared.data(forKey: key),
            var settings = try? JSONDecoder().decode(ParentSettings.self, from: data)
        else {
            return ParentSettings(parentName: "", parentPhoneNumber: "", isCoachEnabledForChild: false)
        }
        settings.resetDailyStateIfNeeded()
        return settings
    }

    func save() {
        guard let data = try? JSONEncoder().encode(self) else { return }
        UserDefaults.shared.set(data, forKey: ParentSettings.key)
    }

    mutating func setPIN(_ pin: String) {
        pinHash = Self.hash(pin)
    }

    func verifyPIN(_ pin: String) -> Bool {
        guard let pinHash else { return true } // pas encore configuré : pas de gate
        return Self.hash(pin) == pinHash
    }

    var hasPIN: Bool { pinHash != nil }

    mutating func grantExtraMinutes(_ minutes: Int) {
        resetDailyStateIfNeeded()
        extraMinutesGrantedToday += minutes
        save()
    }

    private mutating func resetDailyStateIfNeeded() {
        let today = Self.todayString()
        if extraMinutesGrantedDate != today {
            extraMinutesGrantedToday = 0
            extraMinutesGrantedDate = today
        }
    }

    private static func todayString() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }

    private static func generateFamilyCode() -> String {
        let letters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" // sans caractères ambigus (0/O, 1/I)
        return String((0..<6).map { _ in letters.randomElement()! })
    }

    private static func hash(_ text: String) -> String {
        let digest = SHA256.hash(data: Data(text.utf8))
        return digest.compactMap { String(format: "%02x", $0) }.joined()
    }
}
