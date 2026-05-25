// frontend/app/backtest/page.tsx
import { BacktestForm } from "@/components/backtest/backtest-form";

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">백테스트 (SMA Crossover)</h1>
      <BacktestForm />
    </div>
  );
}
