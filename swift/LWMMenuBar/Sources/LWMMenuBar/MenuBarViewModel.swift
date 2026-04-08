import Foundation
import SwiftUI

@MainActor @Observable
final class MenuBarViewModel {
    var score: Double = 0.0
    var previousScore: Double = 0.0
    var grade: String = "—"
    var eventCount: Int = 0
    var patterns: [PatternItem] = []
    var experiments: [ExperimentItem] = []
    var timelineBuckets: [TimelineBucket] = []
    var feedbackItems: [FeedbackItem] = []
    var lastUpdated: Date? = nil
    var errorMessage: String? = nil

    // Suggestions state
    var suggestions: [SuggestionItem] = []
    var isSuggestionsLoading: Bool = false
    var suggestionsError: String? = nil

    // Briefing state
    var briefingText: String? = nil
    var isBriefingLoading: Bool = false
    var showBriefingSheet: Bool = false

    // Quick actions state
    var isCollecting: Bool = false
    var collectResult: String? = nil
    var showExperimentInput: Bool = false
    var experimentDescription: String = ""
    var isStartingExperiment: Bool = false

    // Animation state for score changes
    var scoreAnimationTrigger: Bool = false
    var scoreJustChanged: Bool = false

    var gradeText: String { grade }

    private var refreshTimer: Timer?
    private let dbPath: String

    // MARK: - Display Models

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

    struct SuggestionItem: Identifiable {
        let id: String
        let title: String
        let rationale: String
        let impact: String  // "high", "medium", "low"

        var impactColor: Color {
            switch impact.lowercased() {
            case "high": return .red
            case "medium": return .orange
            case "low": return .blue
            default: return .secondary
            }
        }
    }

    struct FeedbackItem: Identifiable {
        let id: Int64
        let suggestionTitle: String
        let action: String  // "accept" or "reject"
        let timestamp: String

        var icon: String { action == "accept" ? "hand.thumbsup" : "hand.thumbsdown" }
        var color: Color { action == "accept" ? .green : .red }
    }

    // MARK: - Init

    init(dbPath: String? = nil) {
        self.dbPath = dbPath ?? LWMDatabase.defaultPath
        refresh()
        startAutoRefresh()
    }

    // MARK: - Refresh

    func refresh() {
        do {
            let db = try LWMDatabase(path: dbPath)

            eventCount = try db.todayEventCount()

            let oldScore = score
            score = try db.todayProductiveRatio()

            // Detect significant score changes for animation
            if oldScore > 0 && abs(score - oldScore) > 0.05 {
                previousScore = oldScore
                scoreJustChanged = true
                scoreAnimationTrigger.toggle()

                // Notify on significant change
                if abs(score - oldScore) > 0.1 {
                    let newGrade = Self.gradeFromScore(score)
                    LWMNotifications.sendScoreChange(oldScore: oldScore, newScore: score, grade: newGrade)
                }
            }

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

            // Timeline
            timelineBuckets = try db.todayTimeline()

            // Feedback history
            feedbackItems = try db.recentFeedback(limit: 5).map { fb in
                FeedbackItem(
                    id: fb.id,
                    suggestionTitle: fb.suggestionTitle,
                    action: fb.action,
                    timestamp: fb.timestamp
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
            Task { @MainActor in
                self?.refresh()
            }
        }
    }

    // MARK: - Suggestions (shells out to lwm suggest)

    func loadSuggestions() {
        guard !isSuggestionsLoading else { return }
        isSuggestionsLoading = true
        suggestionsError = nil
        suggestions = []

        Task {
            do {
                let output = try await LWMCommandRunner.runAsync(["suggest", "--detail"])
                self.suggestions = Self.parseSuggestions(output)
                if self.suggestions.isEmpty && !output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    self.suggestionsError = output.trimmingCharacters(in: .whitespacesAndNewlines)
                }
            } catch {
                self.suggestionsError = error.localizedDescription
            }
            self.isSuggestionsLoading = false
        }
    }

    func acceptSuggestion(_ id: String) {
        Task {
            do {
                _ = try await LWMCommandRunner.runAsync(["suggest", "--accept", id])
                self.suggestions.removeAll { $0.id == id }
                self.refresh()
            } catch {
                self.suggestionsError = error.localizedDescription
            }
        }
    }

    func rejectSuggestion(_ id: String) {
        Task {
            do {
                _ = try await LWMCommandRunner.runAsync(["suggest", "--reject", id])
                self.suggestions.removeAll { $0.id == id }
                self.refresh()
            } catch {
                self.suggestionsError = error.localizedDescription
            }
        }
    }

    // MARK: - Briefing (shells out to lwm briefing)

    func loadBriefing() {
        guard !isBriefingLoading else { return }
        isBriefingLoading = true
        briefingText = nil

        Task {
            do {
                let output = try await LWMCommandRunner.runAsync(["briefing"])
                self.briefingText = output.trimmingCharacters(in: .whitespacesAndNewlines)
                self.showBriefingSheet = true
            } catch {
                self.briefingText = "Error loading briefing: \(error.localizedDescription)"
                self.showBriefingSheet = true
            }
            self.isBriefingLoading = false
        }
    }

    // MARK: - Quick Actions

    func collectNow() {
        guard !isCollecting else { return }
        isCollecting = true
        collectResult = nil

        Task {
            do {
                let output = try await LWMCommandRunner.runAsync(["collect"])
                self.collectResult = output.trimmingCharacters(in: .whitespacesAndNewlines)
                self.refresh()
            } catch {
                self.collectResult = "Error: \(error.localizedDescription)"
            }
            self.isCollecting = false
        }
    }

    func openDashboard() {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        process.arguments = ["http://localhost:8765"]
        try? process.run()
    }

    func startExperiment() {
        let desc = experimentDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !desc.isEmpty, !isStartingExperiment else { return }
        isStartingExperiment = true

        Task {
            do {
                _ = try await LWMCommandRunner.runAsync(["experiment", "start", desc])
                self.experimentDescription = ""
                self.showExperimentInput = false
                self.refresh()
            } catch {
                self.errorMessage = error.localizedDescription
            }
            self.isStartingExperiment = false
        }
    }

    // MARK: - Parse Helpers

    /// Parse CLI output like:
    /// 1. [HIGH] Title here  (id: abc123)
    ///    Rationale text
    ///    Type: ... | Delta: ...
    static func parseSuggestions(_ output: String) -> [SuggestionItem] {
        var items: [SuggestionItem] = []
        let lines = output.components(separatedBy: "\n")
        var i = 0
        while i < lines.count {
            let line = lines[i].trimmingCharacters(in: .whitespaces)
            // Match: "1. [HIGH] Title text  (id: abc123)"
            if let match = line.range(of: #"^\d+\.\s+\[(\w+)\]\s+(.+?)\s+\(id:\s+(\S+)\)"#, options: .regularExpression) {
                let matchStr = String(line[match])
                let impactRange = matchStr.range(of: #"\[(\w+)\]"#, options: .regularExpression)!
                let impact = String(matchStr[impactRange])
                    .replacingOccurrences(of: "[", with: "")
                    .replacingOccurrences(of: "]", with: "")
                    .lowercased()

                let idRange = matchStr.range(of: #"\(id:\s+(\S+)\)"#, options: .regularExpression)!
                let idStr = String(matchStr[idRange])
                    .replacingOccurrences(of: "(id: ", with: "")
                    .replacingOccurrences(of: ")", with: "")

                // Extract title: between "] " and "  (id:"
                let afterBracket = line.components(separatedBy: "] ").dropFirst().joined(separator: "] ")
                let title = afterBracket.components(separatedBy: "  (id:").first?.trimmingCharacters(in: .whitespaces) ?? ""

                // Next line is rationale
                var rationale = ""
                if i + 1 < lines.count {
                    rationale = lines[i + 1].trimmingCharacters(in: .whitespaces)
                }

                items.append(SuggestionItem(id: idStr, title: title, rationale: rationale, impact: impact))
            }
            i += 1
        }
        return items
    }

    // MARK: - Score Helpers

    static func gradeFromScore(_ score: Double) -> String {
        switch score {
        case 0.8...: return "A"
        case 0.65..<0.8: return "B"
        case 0.5..<0.65: return "C"
        case 0.35..<0.5: return "D"
        default: return "F"
        }
    }

    static func parseDate(_ s: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: s)
    }
}
