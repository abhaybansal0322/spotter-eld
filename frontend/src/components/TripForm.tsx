import { useId, useState, type FormEvent, type ReactNode } from 'react';

import { hoursFigure } from '../lib/format';
import {
  EMPTY_TRIP_FORM,
  HOME_TERMINAL_ZONES,
  remainingCycleHours,
  toTripPlanRequest,
  validateTripForm,
  type FieldErrors,
  type TripFormValues,
} from '../lib/tripForm';
import type { TripPlanRequest } from '../types';
import './TripForm.css';

export interface TripFormProps {
  onSubmit: (request: TripPlanRequest) => void;
  loading: boolean;
  /** Field errors from the server; shown inline against their inputs. */
  fieldErrors?: FieldErrors;
  /** Cycle limit in hours from the backend. Null until it arrives, or if it never does: the server then enforces it. */
  cycleLimitHours: number | null;
}

type TextField = 'current_location' | 'pickup_location' | 'dropoff_location';

export function TripForm({ onSubmit, loading, fieldErrors, cycleLimitHours }: TripFormProps) {
  const id = useId();
  const [values, setValues] = useState<TripFormValues>(EMPTY_TRIP_FORM);
  const [clientErrors, setClientErrors] = useState<FieldErrors>({});
  const errors = Object.keys(clientErrors).length > 0 ? clientErrors : (fieldErrors ?? {});
  const remaining = cycleLimitHours === null ? null : remainingCycleHours(values.current_cycle_used, cycleLimitHours);

  const set = (field: keyof TripFormValues) => (value: string) => setValues((current) => ({ ...current, [field]: value }));

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problems = validateTripForm(values, cycleLimitHours);
    setClientErrors(problems);
    if (Object.keys(problems).length === 0) {
      onSubmit(toTripPlanRequest(values));
    }
  };

  const location = (field: TextField, label: string, placeholder: string) => (
    <Field id={`${id}-${field}`} label={label} errors={errors[field]}>
      {(props) => (
        <input
          {...props}
          type="text"
          name={field}
          autoComplete="off"
          placeholder={placeholder}
          value={values[field]}
          onChange={(event) => set(field)(event.target.value)}
        />
      )}
    </Field>
  );

  return (
    <form className="trip-form" onSubmit={submit} noValidate aria-label="Trip details">
      <div className="trip-form__intro">
        <p className="eyebrow">New trip</p>
        <h2 className="trip-form__title">Route and hours</h2>
      </div>

      {location('current_location', 'Current location', 'City, ST or street address')}
      {location('pickup_location', 'Pickup location', 'Shipper city or address')}
      {location('dropoff_location', 'Dropoff location', 'Receiver city or address')}

      <Field id={`${id}-current_cycle_used`} label="Current cycle used" errors={errors.current_cycle_used}>
        {(props) => (
          <div className="trip-form__cycle">
            <div className="trip-form__cycle-row">
              <input
                {...props}
                className="trip-form__cycle-number figure"
                type="number"
                name="current_cycle_used"
                inputMode="decimal"
                min={0}
                max={cycleLimitHours ?? undefined}
                step={0.25}
                value={values.current_cycle_used}
                onChange={(event) => set('current_cycle_used')(event.target.value)}
              />
              <span className="trip-form__unit">{cycleLimitHours === null ? 'hours' : `hours of ${cycleLimitHours}`}</span>
            </div>
            {/* A slider needs a range, so it only appears once the limit is known. */}
            {cycleLimitHours !== null && (
              <input
                className="trip-form__slider"
                type="range"
                aria-label="Current cycle used, slider"
                min={0}
                max={cycleLimitHours}
                step={0.25}
                value={remaining === null ? 0 : values.current_cycle_used}
                onChange={(event) => set('current_cycle_used')(event.target.value)}
              />
            )}
            {cycleLimitHours !== null && (
              <p className="trip-form__hint" aria-live="polite">
                {remaining === null ? 'Enter a number of hours.' : <><span className="figure">{hoursFigure(remaining)}</span> h left in the cycle</>}
              </p>
            )}
          </div>
        )}
      </Field>

      <details className="trip-form__advanced">
        <summary>Advanced</summary>
        <Field id={`${id}-start_time`} label="Start time" errors={errors.start_time}>
          {(props) => (
            <>
              <input
                {...props}
                type="datetime-local"
                name="start_time"
                step={900}
                value={values.start_time}
                onChange={(event) => set('start_time')(event.target.value)}
              />
              <p className="trip-form__hint">Home terminal time. Leave blank to start now; rounded down to 15 minutes.</p>
            </>
          )}
        </Field>
        <Field id={`${id}-timezone`} label="Home terminal time zone" errors={errors.timezone}>
          {(props) => (
            <select {...props} name="timezone" value={values.timezone} onChange={(event) => set('timezone')(event.target.value)}>
              {HOME_TERMINAL_ZONES.map((zone) => (
                <option key={zone.value} value={zone.value}>
                  {zone.label}
                </option>
              ))}
            </select>
          )}
        </Field>
      </details>

      <button className="button trip-form__submit" type="submit" disabled={loading}>
        {loading ? 'Planning trip…' : 'Plan trip'}
      </button>
    </form>
  );
}

interface ControlProps {
  id: string;
  'aria-invalid': boolean;
  'aria-describedby': string | undefined;
}

function Field({ id, label, errors, children }: { id: string; label: string; errors?: string[]; children: (props: ControlProps) => ReactNode }) {
  const errorId = `${id}-error`;
  const invalid = errors !== undefined && errors.length > 0;
  return (
    <div className={invalid ? 'trip-form__field trip-form__field--invalid' : 'trip-form__field'}>
      <label className="trip-form__label" htmlFor={id}>
        {label}
      </label>
      {children({ id, 'aria-invalid': invalid, 'aria-describedby': invalid ? errorId : undefined })}
      {invalid && (
        <p className="trip-form__error" id={errorId}>
          {errors.join(' ')}
        </p>
      )}
    </div>
  );
}
