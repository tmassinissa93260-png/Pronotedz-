import Foundation
import CloudKit

/// Fait transiter une demande "plus de temps" entre l'appareil de l'enfant
/// et celui du parent via une base CloudKit publique, identifiée par le code
/// famille (ParentSettings.familyCode) — même mécanique que SchoolSync côté
/// école, jamais compilée/testée ici (pas de Xcode disponible).
///
/// AVERTISSEMENT SÉCURITÉ, plus sérieux ici que côté école : ce flux
/// contrôle un vrai accès (accorder plus de temps d'écran), pas juste
/// l'affichage de statistiques. Une base CloudKit publique non durcie
/// (Security Roles, voir README-SETUP.md) laisse n'importe quel utilisateur
/// de l'app capable de lire/modifier une demande s'il devine ou intercepte
/// un code famille — y compris, dans le pire cas, approuver sa propre
/// demande. Ne pas utiliser tel quel avec un vrai enfant sans durcissement
/// préalable.
///
/// Deuxième incertitude à vérifier : la notification quasi temps réel côté
/// parent suppose une CKQuerySubscription + push distant configurée dans
/// Xcode (capacité Push Notifications + Background Modes → Remote
/// notifications). Sans ça, ce code fonctionne uniquement par rafraîchissement
/// manuel (bouton "Actualiser"), pas par notification automatique — c'est le
/// repli prévu ici, pas une régression.
enum TimeRequestSync {
    private static let recordType = "TimeRequest"
    private static var database: CKDatabase { CKContainer.default().publicCloudDatabase }

    static func sendRequest(familyCode: String, requestedMinutes: Int) async throws {
        let record = CKRecord(recordType: recordType)
        record["familyCode"] = familyCode
        record["requestedMinutes"] = requestedMinutes
        record["status"] = "pending"
        record["date"] = todayString()
        record["createdAt"] = Date()
        _ = try await database.save(record)
    }

    static func fetchRequests(familyCode: String) async throws -> [TimeRequest] {
        let predicate = NSPredicate(format: "familyCode == %@ AND date == %@", familyCode, todayString())
        let query = CKQuery(recordType: recordType, predicate: predicate)

        let (matchResults, _) = try await database.records(matching: query)
        return matchResults.compactMap { recordID, result in
            guard
                let record = try? result.get(),
                let requestedMinutes = record["requestedMinutes"] as? Int,
                let status = record["status"] as? String
            else { return nil }
            return TimeRequest(
                recordID: recordID,
                requestedMinutes: requestedMinutes,
                status: TimeRequest.Status(rawValue: status) ?? .pending,
                grantedMinutes: record["grantedMinutes"] as? Int
            )
        }
    }

    static func respond(to request: TimeRequest, approve: Bool, grantedMinutes: Int) async throws {
        let record = try await database.record(for: request.recordID)
        record["status"] = approve ? "approved" : "denied"
        record["grantedMinutes"] = approve ? grantedMinutes : 0
        _ = try await database.save(record)
    }

    /// Appelé côté enfant : récupère les demandes approuvées pas encore
    /// appliquées, applique le temps accordé, puis marque comme consommées
    /// pour éviter de les appliquer deux fois.
    static func applyApprovedRequests(familyCode: String) async {
        guard let requests = try? await fetchRequests(familyCode: familyCode) else { return }
        for request in requests where request.status == .approved {
            FrictionScheduler.grantExtraTime(minutes: request.grantedMinutes ?? request.requestedMinutes)
            try? await markConsumed(request)
        }
    }

    private static func markConsumed(_ request: TimeRequest) async throws {
        let record = try await database.record(for: request.recordID)
        record["status"] = "consumed"
        _ = try await database.save(record)
    }

    private static func todayString() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }
}

struct TimeRequest: Identifiable {
    let recordID: CKRecord.ID
    var id: String { recordID.recordName }
    let requestedMinutes: Int
    let status: Status
    var grantedMinutes: Int?

    enum Status: String {
        case pending
        case approved
        case denied
        case consumed
    }
}
