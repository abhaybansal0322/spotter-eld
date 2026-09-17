import './states.css';

export interface ErrorStateProps {
  message: string;
  fieldErrors?: Record<string, string[]>;
  onRetry?: () => void;
}

function fieldName(field: string): string {
  const words = field.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** A readable failure with any per-field problems listed, and a way to try again. */
export function ErrorState({ message, fieldErrors, onRetry }: ErrorStateProps) {
  const fields = Object.entries(fieldErrors ?? {});

  return (
    <div className="state state--error" role="alert">
      <div>
        <p className="state__title">We couldn&rsquo;t plan this trip</p>
        <p className="state__detail">{message}</p>
        {fields.length > 0 && (
          <ul className="state__fields">
            {fields.map(([field, messages]) => (
              <li key={field}>
                <strong>{fieldName(field)}:</strong> {messages.join(' ')}
              </li>
            ))}
          </ul>
        )}
        {onRetry && (
          <button type="button" className="state__retry" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
