import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo?.componentStack)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-paper text-ink flex items-center justify-center p-6 font-sans">
          <div className="bg-surface border border-line rounded p-6 max-w-lg w-full">
            <h1 className="text-base font-semibold text-ink mb-2">Something went wrong</h1>
            <p className="text-xs text-muted mb-4">
              An unexpected error occurred while rendering the application.
            </p>
            {this.state.error?.message && (
              <pre className="text-xs bg-paper text-negative p-3 rounded border border-line overflow-x-auto mb-4 font-mono whitespace-pre-wrap">
                {this.state.error.message}
              </pre>
            )}
            <button
              type="button"
              onClick={this.handleReload}
              className="px-3 py-1.5 text-xs font-medium bg-surface text-ink border border-line rounded hover:bg-paper transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
