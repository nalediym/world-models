import SwiftUI

@main
struct LWMMenuBarApp: App {
    @State private var viewModel = MenuBarViewModel()

    var body: some Scene {
        MenuBarExtra {
            MenuBarPopover(viewModel: viewModel)
        } label: {
            HStack(spacing: 2) {
                Image(systemName: "brain.head.profile")
                Text(viewModel.gradeText)
                    .font(.caption.monospacedDigit())
            }
        }
        .menuBarExtraStyle(.window)
    }
}
