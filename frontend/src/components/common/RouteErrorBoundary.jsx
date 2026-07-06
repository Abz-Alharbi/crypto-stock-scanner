import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export default class RouteErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    this.setState({ info });
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="bg-scanner-card border border-scanner-danger/30 rounded-2xl p-10 text-center">
        <AlertCircle size={40} className="mx-auto text-scanner-danger mb-3" />
        <h3 className="font-display text-xl font-bold text-scanner-danger">Page Error</h3>
        <p className="text-sm text-scanner-text-dim mt-2">
          This route could not render correctly.
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null, info: null })}
          className="inline-flex items-center gap-2 mt-5 px-4 py-2 rounded-lg bg-scanner-accent text-scanner-bg text-sm font-semibold"
        >
          <RotateCcw size={14} />
          Try Again
        </button>
      </div>
    );
  }
}
