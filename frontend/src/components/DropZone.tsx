"use client";

import { useId, useState } from "react";

type Props = {
  label: string;
  hint: string;
  accept: string;
  file: File | null;
  onFile: (file: File | null) => void;
};

export default function DropZone({ label, hint, accept, file, onFile }: Props) {
  const inputId = useId();
  const [over, setOver] = useState(false);

  function take(list: FileList | null) {
    const next = list?.[0];
    if (next) onFile(next);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        take(event.dataTransfer.files);
      }}
      className={`flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed bg-white px-6 text-center transition ${
        over ? "border-neutral-950" : "border-neutral-300 hover:border-neutral-900"
      }`}
    >
      <input
        id={inputId}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(event) => take(event.target.files)}
      />
      <label htmlFor={inputId} className="cursor-pointer">
        <span className="block text-sm font-medium">{label}</span>
        <span className="mt-1 block max-w-xs text-sm text-neutral-500">{file ? file.name : hint}</span>
      </label>
    </div>
  );
}
