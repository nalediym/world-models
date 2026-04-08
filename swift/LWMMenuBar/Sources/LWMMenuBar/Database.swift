import Foundation
import GRDB

// MARK: - Models (read-only, matching Python's SQLite schema)

struct RawEvent: Codable, FetchableRecord, TableRecord {
    static let databaseTableName = "raw_events"

    let id: Int64
    let timestamp: String
    let source: String
    let title: String?
    let domain: String?
    let url: String?
    let durationSeconds: Double?
    let metadata: String?

    enum CodingKeys: String, CodingKey {
        case id, timestamp, source, title, domain, url
        case durationSeconds = "duration_seconds"
        case metadata
    }
}

struct DiscoveredPattern: Codable, FetchableRecord, TableRecord {
    static let databaseTableName = "discovered_patterns"

    let name: String
    let category: String
    let description: String
    let evidence: String
    let confidence: Double
    let daysObserved: Int
    let firstSeen: String?
    let lastSeen: String?

    enum CodingKeys: String, CodingKey {
        case name, category, description, evidence, confidence
        case daysObserved = "days_observed"
        case firstSeen = "first_seen"
        case lastSeen = "last_seen"
    }
}

struct Experiment: Codable, FetchableRecord, TableRecord {
    static let databaseTableName = "experiments"

    let id: String
    let description: String
    let intervention: String
    let durationDays: Int
    let startDate: String
    let status: String
    let baselineScore: Double?
    let resultScore: Double?
    let resultSummary: String?

    enum CodingKeys: String, CodingKey {
        case id, description, intervention, status
        case durationDays = "duration_days"
        case startDate = "start_date"
        case baselineScore = "baseline_score"
        case resultScore = "result_score"
        case resultSummary = "result_summary"
    }
}

struct SuggestionFeedback: Codable, FetchableRecord, TableRecord {
    static let databaseTableName = "suggestion_feedback"

    let id: Int64
    let suggestionId: String
    let suggestionTitle: String
    let action: String
    let timestamp: String
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case id
        case suggestionId = "suggestion_id"
        case suggestionTitle = "suggestion_title"
        case action, timestamp, notes
    }
}

// MARK: - Database Reader

final class LWMDatabase: Sendable {
    private let dbPool: DatabasePool

    init(path: String) throws {
        var config = Configuration()
        config.readonly = true
        dbPool = try DatabasePool(path: path, configuration: config)
    }

    /// Default database path (matches Python's default)
    static var defaultPath: String {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return "\(home)/Projects/world-models/data/raw/life_world_model.sqlite3"
    }

    // MARK: - Queries

    func todayEventCount() throws -> Int {
        let today = Self.todayPrefix()
        return try dbPool.read { db in
            try RawEvent.filter(Column("timestamp") >= today).fetchCount(db)
        }
    }

    func topPatterns(limit: Int = 5) throws -> [DiscoveredPattern] {
        try dbPool.read { db in
            try DiscoveredPattern
                .order(Column("confidence").desc)
                .limit(limit)
                .fetchAll(db)
        }
    }

    func activeExperiments() throws -> [Experiment] {
        try dbPool.read { db in
            try Experiment
                .filter(Column("status") == "active")
                .order(Column("start_date").desc)
                .fetchAll(db)
        }
    }

    func completedExperiments(limit: Int = 3) throws -> [Experiment] {
        try dbPool.read { db in
            try Experiment
                .filter(Column("status") == "completed")
                .order(Column("start_date").desc)
                .limit(limit)
                .fetchAll(db)
        }
    }

    func recentFeedback(limit: Int = 10) throws -> [SuggestionFeedback] {
        try dbPool.read { db in
            try SuggestionFeedback
                .order(Column("timestamp").desc)
                .limit(limit)
                .fetchAll(db)
        }
    }

    /// Compute a rough day score: productive events / total events
    /// (Simplified version — the real scoring happens in Python)
    func todayProductiveRatio() throws -> Double {
        let today = Self.todayPrefix()
        let productiveDomains = ["github.com", "arxiv.org", "stackoverflow.com"]

        return try dbPool.read { db in
            let total = try RawEvent
                .filter(Column("timestamp") >= today)
                .fetchCount(db)
            guard total > 0 else { return 0.0 }

            let productive = try RawEvent
                .filter(Column("timestamp") >= today)
                .filter(productiveDomains.contains(Column("domain")))
                .fetchCount(db)

            return Double(productive) / Double(total)
        }
    }

    // MARK: - Helpers

    private static func todayPrefix() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }
}
