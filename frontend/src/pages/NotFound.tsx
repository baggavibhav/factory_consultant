import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="center-page">
      <div>
        <h1 className="h1">This page doesn't exist</h1>
        <p className="muted">The link may be old, or the project was deleted.</p>
        <Link to="/" className="btn primary">Go to projects</Link>
      </div>
    </div>
  );
}
