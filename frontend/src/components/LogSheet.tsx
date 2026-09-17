import type { ReactNode } from 'react';

import { dateParts, hoursFigure, milesLabel } from '../lib/format';
import type { RequiredLimits } from '../lib/limits';
import type { DaySheet } from '../types';
import { LogGrid } from './LogGrid';
import './LogSheet.css';

export interface LogSheetProps {
  day: DaySheet;
  timezone: string;
  limits: RequiredLimits;
}

/** One Driver's Daily Log page, laid out after the blank paper form, with the duty grid embedded. */
export function LogSheet({ day, timezone, limits }: LogSheetProps) {
  const { header, recap } = day;
  const date = dateParts(day.date);

  return (
    <article className="log-sheet" aria-label={`Driver's daily log for ${day.date}`}>
      <header className="log-sheet__title-block">
        <div className="log-sheet__title">
          <h2>Driver&rsquo;s Daily Log</h2>
          <span className="log-sheet__caption">(24 hours)</span>
        </div>

        <div className="log-sheet__date" aria-label="Date">
          <DateBox value={date.month} caption="(month)" part="month" />
          <span className="log-sheet__date-slash">/</span>
          <DateBox value={date.day} caption="(day)" part="day" />
          <span className="log-sheet__date-slash">/</span>
          <DateBox value={date.year} caption="(year)" part="year" />
        </div>

        <p className="log-sheet__copies">
          <span>Original &ndash; File at home terminal.</span>
          <span>Duplicate &ndash; Driver retains in his/her possession for 8 days.</span>
        </p>
      </header>

      <div className="log-sheet__route">
        <Ruled label="From:" value={header.from} inline />
        <Ruled label="To:" value={header.to} inline />
      </div>

      <div className="log-sheet__particulars">
        <div className="log-sheet__mileage">
          <Boxed caption="Total Miles Driving Today" value={milesLabel(day.total_miles_driving)} field="total-miles-driving" />
          <Boxed caption="Total Mileage Today" value={milesLabel(header.total_mileage_today)} field="total-mileage" />
          <Boxed
            caption="Truck/Tractor and Trailer Numbers or License Plate(s)/State (show each unit)"
            value={header.vehicle_numbers}
            field="vehicle-numbers"
            wide
          />
        </div>
        <div className="log-sheet__carrier">
          <Ruled label="Name of Carrier or Carriers" value={header.carrier_name} />
          <Ruled label="Main Office Address" value={header.main_office_address} />
          <Ruled label="Home Terminal Address" value={header.home_terminal_address} />
        </div>
      </div>

      <LogGrid segments={day.segments} totals={day.totals} remarks={day.remarks} limits={limits} />

      <section className="log-sheet__remarks" aria-label="Remarks">
        <div className="log-sheet__shipping">
          <p className="log-sheet__shipping-title">Shipping Documents:</p>
          <Ruled label="DVL or Manifest No. or" value={header.shipping_document} />
          <Ruled label="Shipper &amp; Commodity" value={null} />
        </div>
        <div className="log-sheet__signatures">
          <Ruled label="Driver's signature (I certify these entries are true and correct)" value={header.driver_name} />
          <Ruled label="Name of co-driver" value={header.co_driver} />
        </div>
        <p className="log-sheet__instruction">
          Enter name of place you reported and where released from work and when and where each change of duty
          occurred.
          <br />
          Use time standard of home terminal <span className="log-sheet__timezone">({timezone})</span>.
        </p>
      </section>

      <section className="log-sheet__recap" aria-label="Recap">
        <div className="log-sheet__recap-intro">
          <strong>Recap:</strong> Complete at end of day
        </div>
        <RecapBox
          field="on-duty-today"
          value={hoursFigure(recap.on_duty_today_hours)}
          caption="On duty hours today, Total lines 3 & 4"
        />

        <div className="log-sheet__cycle" data-cycle="70-8">
          <div className="log-sheet__cycle-title">70 Hour/ 8 Day Drivers</div>
          <RecapBox
            letter="A."
            field="a"
            value={hoursFigure(recap.a_on_duty_last_7_days_hours)}
            caption="A. Total hours on duty last 7 days including today."
          />
          <RecapBox
            letter="B."
            field="b"
            value={hoursFigure(recap.b_available_tomorrow_hours)}
            caption="B. Total hours available tomorrow 70 hr. minus A*"
          />
          <RecapBox
            letter="C."
            field="c"
            value={hoursFigure(recap.c_on_duty_last_5_days_hours)}
            caption="C. Total hours on duty last 5 days including today."
          />
        </div>

        <div className="log-sheet__cycle log-sheet__cycle--unused" data-cycle="60-7">
          <div className="log-sheet__cycle-title">60 Hour/ 7 Day Drivers</div>
          <RecapBox letter="A." field="60-a" value={null} caption="A. Total hours on duty last 8 days including today." />
          <RecapBox letter="B." field="60-b" value={null} caption="B. Total hours available tomorrow 60 hr. minus A*" />
          <RecapBox letter="C." field="60-c" value={null} caption="C. Total hours on duty last 7 days including today." />
        </div>

        <p className="log-sheet__restart-note">
          *If you took 34 consecutive hours off duty you have 60/70 hours available
        </p>
      </section>
    </article>
  );
}

function DateBox({ value, caption, part }: { value: string; caption: string; part: string }) {
  return (
    <span className="log-sheet__date-part">
      <span className="log-sheet__date-value" data-date-part={part}>
        {value}
      </span>
      <span className="log-sheet__caption">{caption}</span>
    </span>
  );
}

/** A printed label over a ruled line. A null value leaves the line blank, as on an unfilled form. */
function Ruled({ label, value, inline = false }: { label: ReactNode; value: string | null; inline?: boolean }) {
  return (
    <div className={inline ? 'log-sheet__ruled log-sheet__ruled--inline' : 'log-sheet__ruled'}>
      {inline && <span className="log-sheet__label">{label}</span>}
      <span className="log-sheet__line">{value ?? ''}</span>
      {!inline && <span className="log-sheet__label">{label}</span>}
    </div>
  );
}

function Boxed({ caption, value, field, wide = false }: { caption: string; value: string | null; field: string; wide?: boolean }) {
  return (
    <div className={wide ? 'log-sheet__boxed log-sheet__boxed--wide' : 'log-sheet__boxed'}>
      <span className="log-sheet__box" data-field={field}>
        {value ?? ''}
      </span>
      <span className="log-sheet__label">{caption}</span>
    </div>
  );
}

function RecapBox({ letter, field, value, caption }: { letter?: string; field: string; value: string | null; caption: string }) {
  return (
    <div className="log-sheet__recap-box">
      {letter && <span className="log-sheet__recap-letter">{letter}</span>}
      <span className="log-sheet__recap-value" data-recap={field}>
        {value ?? ''}
      </span>
      <span className="log-sheet__recap-caption">{caption}</span>
    </div>
  );
}
