import Foundation
import CloudKit

/// Fait remonter, une fois par jour, un seul chiffre par élève (le nombre de
/// réouvertures forcées, déjà suivi localement par SessionState) vers une
/// base CloudKit publique lisible par l'enseignant. Volontairement PAS de
/// détail par app : cette donnée-là vit dans l'extension DeviceActivityReport,
/// dont Apple restreint la sortie précisément pour empêcher ce genre
/// d'exfiltration vers un tiers — voir la note en tête de fichier de
/// DeviceActivityReportExtension.swift. Non compilé/testé ici (pas de Xcode) :
/// l'API CloudKit ci-dessous est reconstituée de mémoire, raisonnablement
/// stable mais à vérifier.
///
/// ATTENTION SÉCURITÉ — à ne pas ignorer avant un vrai déploiement : une base
/// CloudKit "publique" est, par défaut, lisible ET modifiable par n'importe
/// quel utilisateur de l'app qui connaît (ou devine) un code de classe. Ça
/// veut dire que sans durcissement des "Security Roles" dans le CloudKit
/// Dashboard (restreindre l'écriture, valider les codes de classe côté
/// serveur), n'importe qui peut lire les chiffres d'une classe ou en injecter
/// de faux. Ce fichier ne fait PAS ce durcissement — à traiter avant toute
/// utilisation avec de vrais élèves, ce n'est pas une option secondaire.
enum SchoolSync {
    private static let recordType = "ClassCheckIn"
    private static var database: CKDatabase { CKContainer.default().publicCloudDatabase }

    static func pushDailyCheckIn(membership: ClassMembership, overridesToday: Int) async {
        let record = CKRecord(recordType: recordType)
        record["classCode"] = membership.classCode
        record["studentName"] = membership.displayName
        record["overridesToday"] = overridesToday
        record["date"] = Self.todayString()

        do {
            _ = try await database.save(record)
        } catch {
            print("Envoi CloudKit échoué (pas grave si hors-ligne, on réessaiera demain) : \(error)")
        }
    }

    static func fetchClassCheckIns(classCode: String) async throws -> [StudentCheckIn] {
        let predicate = NSPredicate(format: "classCode == %@ AND date == %@", classCode, Self.todayString())
        let query = CKQuery(recordType: recordType, predicate: predicate)

        let (matchResults, _) = try await database.records(matching: query)
        return matchResults.compactMap { _, result in
            guard
                let record = try? result.get(),
                let name = record["studentName"] as? String,
                let overrides = record["overridesToday"] as? Int
            else { return nil }
            return StudentCheckIn(studentName: name, overridesToday: overrides)
        }
    }

    private static func todayString() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }
}

struct StudentCheckIn: Identifiable {
    var id: String { studentName }
    let studentName: String
    let overridesToday: Int
}
