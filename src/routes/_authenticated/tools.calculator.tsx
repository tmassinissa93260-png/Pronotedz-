import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/tools/calculator")({
  component: CalculatorPage,
});

type Op = "+" | "-" | "×" | "÷" | "xʸ";

function CalculatorPage() {
  const [display, setDisplay] = useState("0");
  const [accumulator, setAccumulator] = useState<number | null>(null);
  const [pendingOp, setPendingOp] = useState<Op | null>(null);
  const [memory, setMemory] = useState(0);
  const [degrees, setDegrees] = useState(true);
  const [freshInput, setFreshInput] = useState(true);

  const current = parseFloat(display) || 0;

  function inputDigit(d: string) {
    if (freshInput) {
      setDisplay(d === "." ? "0." : d);
      setFreshInput(false);
    } else {
      if (d === "." && display.includes(".")) return;
      setDisplay(display === "0" && d !== "." ? d : display + d);
    }
  }

  function applyOp(op: Op) {
    setAccumulator((prev) => {
      if (prev === null) return current;
      return compute(prev, current, pendingOp);
    });
    setPendingOp(op);
    setFreshInput(true);
  }

  function compute(a: number, b: number, op: Op | null): number {
    switch (op) {
      case "+":
        return a + b;
      case "-":
        return a - b;
      case "×":
        return a * b;
      case "÷":
        return b === 0 ? NaN : a / b;
      case "xʸ":
        return Math.pow(a, b);
      default:
        return b;
    }
  }

  function handleEquals() {
    if (pendingOp === null || accumulator === null) return;
    const result = compute(accumulator, current, pendingOp);
    setDisplay(formatResult(result));
    setAccumulator(null);
    setPendingOp(null);
    setFreshInput(true);
  }

  function formatResult(n: number): string {
    if (Number.isNaN(n)) return "Erreur";
    if (!Number.isFinite(n)) return "Erreur";
    return String(Math.round(n * 1e10) / 1e10);
  }

  function unary(fn: (n: number) => number) {
    setDisplay(formatResult(fn(current)));
    setFreshInput(true);
  }

  function clearAll() {
    setDisplay("0");
    setAccumulator(null);
    setPendingOp(null);
    setFreshInput(true);
  }

  function backspace() {
    if (freshInput) return;
    const next = display.slice(0, -1);
    setDisplay(next === "" || next === "-" ? "0" : next);
  }

  const toRad = (n: number) => (degrees ? (n * Math.PI) / 180 : n);

  const sciButtons: { label: string; onClick: () => void }[] = [
    { label: "sin", onClick: () => unary((n) => Math.sin(toRad(n))) },
    { label: "cos", onClick: () => unary((n) => Math.cos(toRad(n))) },
    { label: "tan", onClick: () => unary((n) => Math.tan(toRad(n))) },
    { label: degrees ? "DEG" : "RAD", onClick: () => setDegrees((d) => !d) },
    { label: "log", onClick: () => unary((n) => Math.log10(n)) },
    { label: "ln", onClick: () => unary((n) => Math.log(n)) },
    { label: "√x", onClick: () => unary((n) => Math.sqrt(n)) },
    { label: "x²", onClick: () => unary((n) => n * n) },
    { label: "xʸ", onClick: () => applyOp("xʸ") },
    { label: "π", onClick: () => { setDisplay(String(Math.PI)); setFreshInput(true); } },
    { label: "e", onClick: () => { setDisplay(String(Math.E)); setFreshInput(true); } },
    { label: "1/x", onClick: () => unary((n) => 1 / n) },
  ];

  const memButtons = [
    { label: "MC", onClick: () => setMemory(0) },
    { label: "MR", onClick: () => { setDisplay(String(memory)); setFreshInput(true); } },
    { label: "M+", onClick: () => setMemory((m) => m + current) },
    { label: "M-", onClick: () => setMemory((m) => m - current) },
  ];

  return (
    <div className="mx-auto max-w-sm px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-bold tracking-tight">Calculatrice</h1>

      <Card className="mt-6 overflow-hidden p-0">
        <div className="bg-secondary/40 px-5 py-6 text-right">
          <div className="h-4 text-xs text-muted-foreground">
            {accumulator !== null && pendingOp ? `${formatResult(accumulator)} ${pendingOp}` : ""}
          </div>
          <div className="mt-1 truncate font-mono text-3xl font-semibold" dir="ltr">
            {display}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-px bg-border p-px text-xs">
          {memButtons.map((b) => (
            <CalcButton key={b.label} label={b.label} onClick={b.onClick} muted />
          ))}
        </div>
        <div className="grid grid-cols-4 gap-px bg-border p-px text-xs">
          {sciButtons.map((b) => (
            <CalcButton key={b.label} label={b.label} onClick={b.onClick} muted />
          ))}
        </div>

        <div className="grid grid-cols-4 gap-px bg-border p-px text-lg">
          <CalcButton label="C" onClick={clearAll} accent />
          <CalcButton label="⌫" onClick={backspace} accent />
          <CalcButton label="%" onClick={() => unary((n) => n / 100)} accent />
          <CalcButton label="÷" onClick={() => applyOp("÷")} accent />

          <CalcButton label="7" onClick={() => inputDigit("7")} />
          <CalcButton label="8" onClick={() => inputDigit("8")} />
          <CalcButton label="9" onClick={() => inputDigit("9")} />
          <CalcButton label="×" onClick={() => applyOp("×")} accent />

          <CalcButton label="4" onClick={() => inputDigit("4")} />
          <CalcButton label="5" onClick={() => inputDigit("5")} />
          <CalcButton label="6" onClick={() => inputDigit("6")} />
          <CalcButton label="-" onClick={() => applyOp("-")} accent />

          <CalcButton label="1" onClick={() => inputDigit("1")} />
          <CalcButton label="2" onClick={() => inputDigit("2")} />
          <CalcButton label="3" onClick={() => inputDigit("3")} />
          <CalcButton label="+" onClick={() => applyOp("+")} accent />

          <CalcButton label="±" onClick={() => { setDisplay(String(-current)); setFreshInput(true); }} />
          <CalcButton label="0" onClick={() => inputDigit("0")} />
          <CalcButton label="." onClick={() => inputDigit(".")} />
          <CalcButton label="=" onClick={handleEquals} primary />
        </div>
      </Card>
    </div>
  );
}

function CalcButton({
  label,
  onClick,
  primary,
  accent,
  muted,
}: {
  label: string;
  onClick: () => void;
  primary?: boolean;
  accent?: boolean;
  muted?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "bg-card py-3.5 font-medium transition-colors hover:bg-secondary/60 active:scale-[0.97]",
        primary && "bg-emerald-gradient text-primary-foreground hover:opacity-90",
        accent && "text-primary",
        muted && "py-2 text-muted-foreground",
      )}
    >
      {label}
    </button>
  );
}
