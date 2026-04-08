import Foundation
import SwiftUI

@Observable
final class MenuBarViewModel {
    var score: Double = 0.0
    var grade: String = "—"
    var eventCount: Int = 0
    var patterns: [PatternItem] = []
    var experiments: [ExperimentItem] = []
    var lastUpdated: Date? = nil
    var errorMessage: String? = nil

    var gradeText: String { grade }

    private var refreshTimer: Timer?
    private let dbPath: String

    struct PatternItem: Identifiable {
        let id: String
        let name: String
        let category: String
        let confidence: Double
        let description: String

        var confidenceText: String { "\(Int(confidence * 100))%" }
        var icon: String {
            switch category {
            case "routine": return "clock"
            case "correlation": return "arrow.triangle.branch"
            case "rhythm": return "waveform.path"
            case "trigger": return "bolt"
            case "time_sink": return "hourglass"
            default: return "questionmark.circle"
            }
        }
    }

    struct ExperimentItem: Identifiable {
        let id: String
        let description: String
        let status: String
        let daysLeft: Int?
        let baselineScore: Double?
        let resultScore: Double?

        var statusIcon: String {
            switch status {
            case "active": return "flask"
            case "completed": return "checkmark.circle"
            case "cancelled": return "xmark.circle"
            default: return "questionmark.circle"
            }
        }
    }

    init(dbPath: String? = nil) {
        self.dbPath = dbPath ?? LWMDatabase.defaultPath
        refresh()
        startAutoRefresh()
    }

    func refresh() {
        do {
            let db = try LWMDatabase(path: dbPath)

            eventCount = try db.todayEventCount()
            score = try db.todayProductiveRatio()
            grade = Self.gradeFromScore(score)

            patterns = try db.topPatterns(limit: 5).map { p in
                PatternItem(
                    id: p.name,
                    name: p.name.replacingOccurrences(of: "_", with: " ").capitalized,
                    category: p.category,
                    confidence: p.confidence,
                    description: p.description
                )
            }

            let active = try db.activeExperiments()
            let completed = try db.completedExperiments(limit: 2)

            experiments = (active + completed).map { e in
                let daysLeft: Int?
                if e.status == "active",
                   let start = Self.parseDate(e.startDate) {
                    let end = Calendar.current.date(byAdding: .day, value: e.durationDays, to: start)!
                    daysLeft = Calendar.current.dateComponents([.day], from: Date(), to: end).day
                } else {
                    daysLeft = nil
                }

                return ExperimentItem(
                    id: e.id,
                    description: e.description,
                    status: e.status,
                    daysLeft: daysLeft,
                    baselineScore: e.baselineScore,
                    resultScore: e.resultScore
                )
            }

            lastUpdated = Date()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func startAutoRefresh(interval: TimeInterval = 60) {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            self?.refresh()
        }
    }

    private static func gradeFromScore(_ score: Double) -> String {
        switch score {
        case 0.8...: return "A"
        case 0.65..<0.8: return "B"
        case 0.5..<0.65: return "C"
        case 0.35..<0.5: return "D"
        default: return "F"
        }
    }

    private static func parseDate(_ s: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: s)
    }
}
