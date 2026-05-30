import { ReactNode } from "react";

export default function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg bg-ksp-panel border border-white/10 p-4">
      <h2 className="mb-3 text-sm font-semibold text-white/80">{title}</h2>
      {children}
    </section>
  );
}
