/**
 * Which module you are standing in.
 *
 * The product sells ten modules and draws twenty-one pages, and until this
 * existed nothing on screen connected the two. Every page opened with a
 * decorative eyebrow — BUSINESS OS, FINANCIAL CONTROL CENTER, THE OPERATING
 * LOOP, twenty-eight of them, none repeating and none saying anything — so a
 * customer looking at Bookkeeping and then at Stock intelligence had no way to
 * know those are two separately priced things rather than two views of one.
 *
 * "I look through the website and every single one seems to be just the same
 * books/inventory, I just don't get how there's ten separate ones" is the
 * report this is answering, and it was a fair one.
 *
 * It sits in the topbar rather than on each page: one place that already knows
 * which tab is open, instead of an edit to twenty files that the twenty-first
 * will forget.
 */

const ALWAYS_ON = "Included with every workspace";

export default function ModuleTag({ moduleKey, catalogue = [], modules = [] }) {
  if (!moduleKey) return null;

  const module = catalogue.find((m) => m.key === moduleKey);
  if (!module) return null;

  // Three modules are never charged for. Saying "$10/mo" beside Settings would
  // be a lie, and saying nothing at all is what got us here.
  if (!module.billable) {
    return (
      <span className="module-tag is-free" title={ALWAYS_ON}>
        {module.name}
      </span>
    );
  }

  const row = modules.find((m) => m.module_key === moduleKey);
  const on = row ? row.enabled : true;

  return (
    <span
      className={`module-tag${on ? "" : " is-off"}`}
      title={
        on
          ? `${module.name} — ${module.tagline}. Part of what you pay for.`
          : `${module.name} is switched off for this workspace.`
      }
    >
      {module.name}
      <span className="module-tag-state" aria-hidden="true">
        {on ? "on" : "off"}
      </span>
    </span>
  );
}
