import SwiftUI

struct MenuBarPopover: View {
    @Bindable var viewModel: MenuBarViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                // Header: score + grade with animation
                header

                Divider()

                // Timeline strip
                timelineSection

                Divider()

                // Patterns
                if !viewModel.patterns.isEmpty {
                    patternsSection
                    Divider()
                } else {
                    emptySection(icon: "waveform.path.ecg", text: "No patterns discovered yet. Collect more data to find your rhythms.")
                    Divider()
                }

                // Suggestions
                suggestionsSection
                Divider()

                // Experiments
                if !viewModel.experiments.isEmpty {
                    experimentsSection
                    Divider()
                } else {
                    emptySection(icon: "flask", text: "No experiments running. Start one to test a habit change.")
                    Divider()
                }

                // Quick Actions
                quickActionsSection

                Divider()

                // Footer
                footer
            }
            .padding(16)
        }
        .frame(width: 340)
        .frame(maxHeight: 560)
        .sheet(isPresented: $viewModel.showBriefingSheet) {
            briefingSheet
        }
    }

    // MARK: - Header with animated grade

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Life World Model")
                    .font(.headline)
                timelineSummaryText
            }
            Spacer()
            gradeView
        }
    }

    private var timelineSummaryText: some View {
        Group {
            if viewModel.eventCount == 0 {
                Text("No events today")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("\(viewModel.eventCount) events today")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var gradeView: some View {
        Text(viewModel.grade)
            .font(.system(size: 36, weight: .bold, design: .rounded))
            .foregroundStyle(gradeColor)
            .scaleEffect(viewModel.scoreJustChanged ? 1.2 : 1.0)
            .animation(.spring(response: 0.4, dampingFraction: 0.5), value: viewModel.scoreAnimationTrigger)
            .onChange(of: viewModel.scoreAnimationTrigger) {
                // Reset the scale after animation
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                    viewModel.scoreJustChanged = false
                }
            }
    }

    // MARK: - Timeline Strip

    private var timelineSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Today's Timeline")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            if viewModel.timelineBuckets.isEmpty {
                HStack {
                    Spacer()
                    Text("No activity recorded yet")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Spacer()
                }
                .padding(.vertical, 4)
            } else {
                TimelineStripView(buckets: viewModel.timelineBuckets)
            }
        }
    }

    // MARK: - Patterns

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

    // MARK: - Suggestions

    private var suggestionsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Suggestions")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    viewModel.loadSuggestions()
                } label: {
                    if viewModel.isSuggestionsLoading {
                        ProgressView()
                            .controlSize(.mini)
                    } else {
                        Label("Generate", systemImage: "sparkles")
                            .font(.caption)
                    }
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isSuggestionsLoading)
            }

            if let error = viewModel.suggestionsError {
                Text(error)
                    .font(.caption2)
                    .foregroundStyle(.red)
                    .lineLimit(2)
            }

            if viewModel.suggestions.isEmpty && !viewModel.isSuggestionsLoading {
                // Show recent feedback if no active suggestions
                if !viewModel.feedbackItems.isEmpty {
                    Text("Recent Feedback")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    ForEach(viewModel.feedbackItems) { fb in
                        HStack(spacing: 6) {
                            Image(systemName: fb.icon)
                                .font(.caption2)
                                .foregroundStyle(fb.color)
                            Text(fb.suggestionTitle)
                                .font(.caption)
                                .lineLimit(1)
                            Spacer()
                        }
                    }
                } else {
                    Text("Tap Generate to get data-driven suggestions")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            } else {
                ForEach(viewModel.suggestions) { suggestion in
                    suggestionRow(suggestion)
                }
            }
        }
    }

    private func suggestionRow(_ s: MenuBarViewModel.SuggestionItem) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text(s.impact.uppercased())
                    .font(.system(size: 8, weight: .bold))
                    .padding(.horizontal, 4)
                    .padding(.vertical, 1)
                    .background(s.impactColor.opacity(0.2))
                    .foregroundStyle(s.impactColor)
                    .clipShape(RoundedRectangle(cornerRadius: 3))
                Text(s.title)
                    .font(.caption)
                    .lineLimit(1)
            }
            Text(s.rationale)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            HStack(spacing: 8) {
                Spacer()
                Button {
                    viewModel.acceptSuggestion(s.id)
                } label: {
                    Label("Accept", systemImage: "hand.thumbsup")
                        .font(.caption2)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.green)

                Button {
                    viewModel.rejectSuggestion(s.id)
                } label: {
                    Label("Reject", systemImage: "hand.thumbsdown")
                        .font(.caption2)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.red)
            }
        }
        .padding(6)
        .background(Color.primary.opacity(0.03))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    // MARK: - Experiments

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

    // MARK: - Quick Actions

    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Quick Actions")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                // Collect Now
                Button {
                    viewModel.collectNow()
                } label: {
                    if viewModel.isCollecting {
                        ProgressView()
                            .controlSize(.mini)
                    } else {
                        Label("Collect", systemImage: "arrow.down.circle")
                    }
                }
                .font(.caption)
                .disabled(viewModel.isCollecting)

                // Briefing
                Button {
                    viewModel.loadBriefing()
                } label: {
                    if viewModel.isBriefingLoading {
                        ProgressView()
                            .controlSize(.mini)
                    } else {
                        Label("Briefing", systemImage: "sun.horizon")
                    }
                }
                .font(.caption)
                .disabled(viewModel.isBriefingLoading)

                // Open Dashboard
                Button {
                    viewModel.openDashboard()
                } label: {
                    Label("Dashboard", systemImage: "chart.bar")
                }
                .font(.caption)
            }
            .buttonStyle(.plain)

            // Start Experiment
            if viewModel.showExperimentInput {
                HStack(spacing: 6) {
                    TextField("e.g. Code 8-10am before email", text: $viewModel.experimentDescription)
                        .font(.caption)
                        .textFieldStyle(.roundedBorder)
                    Button {
                        viewModel.startExperiment()
                    } label: {
                        if viewModel.isStartingExperiment {
                            ProgressView()
                                .controlSize(.mini)
                        } else {
                            Text("Go")
                                .font(.caption.bold())
                        }
                    }
                    .disabled(viewModel.experimentDescription.trimmingCharacters(in: .whitespaces).isEmpty || viewModel.isStartingExperiment)
                    Button {
                        viewModel.showExperimentInput = false
                        viewModel.experimentDescription = ""
                    } label: {
                        Image(systemName: "xmark")
                            .font(.caption)
                    }
                    .buttonStyle(.plain)
                }
            } else {
                Button {
                    viewModel.showExperimentInput = true
                } label: {
                    Label("Start Experiment", systemImage: "flask.fill")
                        .font(.caption)
                }
                .buttonStyle(.plain)
            }

            if let result = viewModel.collectResult {
                Text(result)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
    }

    // MARK: - Briefing Sheet

    private var briefingSheet: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Morning Briefing", systemImage: "sun.horizon.fill")
                    .font(.headline)
                Spacer()
                Button {
                    viewModel.showBriefingSheet = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }

            Divider()

            if let text = viewModel.briefingText {
                ScrollView {
                    Text(text)
                        .font(.body)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                ProgressView("Loading briefing...")
            }

            Spacer()
        }
        .padding(20)
        .frame(width: 400, height: 360)
    }

    // MARK: - Footer

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
                    .lineLimit(1)
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

    // MARK: - Empty State

    private func emptySection(icon: String, text: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(.tertiary)
            Text(text)
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
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

// MARK: - Timeline Strip View

struct TimelineStripView: View {
    let buckets: [TimelineBucket]

    /// Show the last 12 hours in 15-min buckets = 48 slots
    private var displayBuckets: [(hour: Int, minute: Int, count: Int, source: String)] {
        let now = Calendar.current.component(.hour, from: Date())
        let startHour = max(0, now - 11)

        var slots: [(hour: Int, minute: Int, count: Int, source: String)] = []
        for h in startHour...now {
            for m in stride(from: 0, to: 60, by: 15) {
                // Skip future buckets in the current hour
                if h == now {
                    let currentMinute = Calendar.current.component(.minute, from: Date())
                    if m > currentMinute { continue }
                }
                if let bucket = buckets.first(where: { $0.hour == h && $0.minute == m }) {
                    slots.append((h, m, bucket.eventCount, bucket.primarySource))
                } else {
                    slots.append((h, m, 0, "idle"))
                }
            }
        }
        return slots
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 1) {
                ForEach(Array(displayBuckets.enumerated()), id: \.offset) { _, bucket in
                    Rectangle()
                        .fill(colorForSource(bucket.source, count: bucket.count))
                        .frame(height: heightForCount(bucket.count))
                        .frame(maxHeight: 16, alignment: .bottom)
                        .clipShape(RoundedRectangle(cornerRadius: 1))
                        .help("\(String(format: "%02d:%02d", bucket.hour, bucket.minute)) - \(bucket.count) events (\(bucket.source))")
                }
            }
            .frame(height: 16)

            // Hour labels
            HStack(spacing: 0) {
                let now = Calendar.current.component(.hour, from: Date())
                let startHour = max(0, now - 11)
                ForEach(startHour...now, id: \.self) { h in
                    if h % 3 == 0 || h == startHour || h == now {
                        Text("\(h)")
                            .font(.system(size: 7).monospacedDigit())
                            .foregroundStyle(.tertiary)
                    }
                    if h < now {
                        Spacer()
                    }
                }
            }
        }
    }

    private func colorForSource(_ source: String, count: Int) -> Color {
        if count == 0 { return Color.primary.opacity(0.06) }
        switch source {
        case "chrome": return .blue
        case "git": return .green
        case "shell": return .orange
        case "calendar": return .purple
        case "knowledgec": return .gray
        default: return Color.primary.opacity(0.15)
        }
    }

    private func heightForCount(_ count: Int) -> CGFloat {
        if count == 0 { return 3 }
        return min(16, CGFloat(3 + count * 2))
    }
}
