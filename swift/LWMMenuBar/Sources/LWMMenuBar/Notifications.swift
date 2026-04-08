import Foundation
import UserNotifications

/// Native macOS notifications via UNUserNotificationCenter.
/// Replaces Python's osascript hack.
enum LWMNotifications {

    static func requestPermission() {
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if let error {
                print("[notifications] Permission error: \(error)")
            }
        }
    }

    static func send(title: String, body: String, identifier: String? = nil) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let id = identifier ?? UUID().uuidString
        let request = UNNotificationRequest(identifier: id, content: content, trigger: nil)

        UNUserNotificationCenter.current().add(request) { error in
            if let error {
                print("[notifications] Send error: \(error)")
            }
        }
    }

    static func sendScoreChange(oldScore: Double, newScore: Double, grade: String) {
        let direction = newScore > oldScore ? "up" : "down"
        send(
            title: "LWM Score \(direction.capitalized)",
            body: "\(Int(oldScore * 100))% \u{2192} \(Int(newScore * 100))% (\(grade))",
            identifier: "score-change"
        )
    }

    static func sendNewPattern(name: String, description: String, confidence: Double) {
        send(
            title: "New Pattern: \(name)",
            body: "\(description) (\(Int(confidence * 100))% confidence)",
            identifier: "pattern-\(name)"
        )
    }

    static func sendExperimentComplete(description: String, summary: String) {
        send(
            title: "Experiment Complete",
            body: "\(description): \(summary)",
            identifier: "experiment-complete"
        )
    }
}
