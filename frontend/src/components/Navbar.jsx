import React from 'react';
import siddiquiWings from '../assets/siddiqui-wings.png';

export default function Navbar({ onOpenNewDraft, loading }) {
  return (
    <header className="top-navbar">
      <div className="top-navbar-inner">
        <div className="navbar-brand-left">
          <img src={siddiquiWings} alt="Wings Emblem" className="brand-wings-img" />
          <span className="brand-title">Editorial Article & Asset Review Desk</span>
        </div>

        <div className="navbar-brand-right">
          <button
            type="button"
            className="run-pipeline-trigger-btn"
            onClick={onOpenNewDraft}
            title="Start pipeline for a new article draft"
          >
            {loading ? "Pipeline Running..." : "+ New Draft"}
          </button>
        </div>
      </div>
    </header>
  );
}
