"use client";
import { ModelProvider } from "@/types/rfp";

interface ModelToggleProps {
  value: ModelProvider;
  onChange: (value: ModelProvider) => void;
  disabled?: boolean;
}

export function ModelToggle({ value, onChange, disabled }: ModelToggleProps) {
  return (
    <div className="model-toggle">
      <span className="model-toggle__label">Reasoning Model</span>
      <div className="model-toggle__options">
        <button
          id="model-claude"
          onClick={() => onChange("claude")}
          disabled={disabled}
          className={`model-option ${value === "claude" ? "model-option--active" : ""}`}
        >
          <span className="model-option__icon">✦</span>
          <div>
            <div className="model-option__name">Claude 3.5 Sonnet</div>
            <div className="model-option__desc">Anthropic · Primary</div>
          </div>
        </button>
        <button
          id="model-openai"
          onClick={() => onChange("openai")}
          disabled={disabled}
          className={`model-option ${value === "openai" ? "model-option--active model-option--openai" : ""}`}
        >
          <span className="model-option__icon model-option__icon--openai">◉</span>
          <div>
            <div className="model-option__name">GPT-4o</div>
            <div className="model-option__desc">OpenAI · Alternative</div>
          </div>
        </button>
      </div>
    </div>
  );
}
