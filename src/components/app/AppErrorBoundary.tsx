import React from 'react';

type AppErrorBoundaryState = {
  hasError: boolean;
  message: string;
};

class AppErrorBoundary extends React.Component<React.PropsWithChildren, AppErrorBoundaryState> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = {
      hasError: false,
      message: '',
    };
  }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || 'Unknown application error',
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application render error:', error, errorInfo);
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
        <div className="max-w-xl w-full bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-3">The app hit an error while rendering.</h1>
          <p className="text-slate-600 mb-4">
            Refresh the page after restarting the dev server. If the problem keeps happening,
            the message below should help us pinpoint it quickly.
          </p>
          <pre className="bg-slate-900 text-slate-100 rounded-xl p-4 text-sm overflow-x-auto whitespace-pre-wrap">
            {this.state.message}
          </pre>
        </div>
      </div>
    );
  }
}

export default AppErrorBoundary;
