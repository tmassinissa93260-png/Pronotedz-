import DeviceActivity
import SwiftUI

extension DeviceActivityReport.Context {
    static let dailySummary = Self("dailySummary")
}

/// Tourne dans un process séparé et privacy-safe : cette extension voit les
/// données d'usage détaillées, mais l'app principale, elle, ne les voit jamais
/// directement. C'est ici qu'on construit la propre UI de stats (plus lisible
/// que l'écran Temps d'écran natif d'Apple, cf. concept-produit.md section 3).
struct DeviceActivityReportExtension: DeviceActivityReportScene {
    let context: DeviceActivityReport.Context = .dailySummary
    let content: (DailySummaryData) -> DailySummaryView

    func makeConfiguration(
        representing data: DeviceActivityResults<DeviceActivityData>
    ) async -> DailySummaryData {
        var totalDuration: TimeInterval = 0
        for await activityData in data {
            for await segment in activityData.activitySegments {
                totalDuration += segment.totalActivityDuration
            }
        }
        return DailySummaryData(totalDuration: totalDuration)
    }
}

struct DailySummaryData {
    let totalDuration: TimeInterval
}

struct DailySummaryView: View {
    let data: DailySummaryData

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Aujourd'hui")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(formatted(data.totalDuration))
                .font(.title2.bold())
        }
        .padding()
    }

    private func formatted(_ duration: TimeInterval) -> String {
        let minutes = Int(duration) / 60
        return "\(minutes) min sur les apps surveillées"
    }
}
