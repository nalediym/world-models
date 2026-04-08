import SwiftUI

struct MenuBarPopover: View {
    let viewModel: MenuBarViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header: score + grade
            header

            Divider()

            // Patterns
            if !viewModel.patterns.isEmpty {
                patternsSection
                Divider()
            }

            // Experiments
            if !viewModel.experiments.isEmpty {
                experimentsSection
                Divider()
            }

            // Footer
            footer
        }
        .padding(16)
        .frame(width: 320)
    }

    // MARK: - Sections

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Life World Model")
                    .font(.headline)
                Text("\(viewModel.eventCount) events today")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(viewModel.grade)
                .font(.system(size: 36, weight: .bold, design: .rounded))
                .foregroundStyle(gradeColor)
        }
    }

    private var patternsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Top Patterns")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            ForEach(viewModel.patterns) { pattern in
                HStack(spacing: 8) {
                    Image(systemName: pattern.icon)
                        .frame(width: 16)
                        .foregroundStyle(.secondary)
                    Text(pattern.name)
                        .font(.caption)
                        .lineLimit(1)
                    Spacer()
                    Text(pattern.confidenceText)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var experimentsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Experiments")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            ForEach(viewModel.experiments) { exp in
                HStack(spacing: 8) {
                    Image(systemName: exp.statusIcon)
                        .frame(width: 16)
                        .foregroundStyle(exp.status == "active" ? .blue : .secondary)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(exp.description)
                            .font(.caption)
                            .lineLimit(1)
                        if let days = exp.daysLeft, exp.status == "active" {
                            Text("\(days) days left")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        if let result = exp.resultScore, let baseline = exp.baselineScore {
                            let delta = result - baseline
                            Text("\(Int(baseline * 100))% \u{2192} \(Int(result * 100))% (\(delta >= 0 ? "+" : "")\(Int(delta * 100))%)")
                                .font(.caption2.monospacedDigit())
                                .foregroundStyle(delta >= 0 ? .green : .red)
                        }
                    }
                    Spacer()
                }
            }
        }
    }

    private var footer: some View {
        HStack {
            if let updated = viewModel.lastUpdated {
                Text("Updated \(updated, style: .relative) ago")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption2)
                    .foregroundStyle(.red)
            }
            Spacer()
            Button("Refresh") {
                viewModel.refresh()
            }
            .font(.caption)
            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .font(.caption)
        }
    }

    // MARK: - Helpers

    private var gradeColor: Color {
        switch viewModel.grade {
        case "A": return .green
        case "B": return .blue
        case "C": return .yellow
        case "D": return .orange
        default: return .red
        }
    }
}
