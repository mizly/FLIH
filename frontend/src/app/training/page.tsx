import type { Metadata } from "next";
import TrainingDashboard from "@/components/training-dashboard";
import "./training.css";

export const metadata: Metadata = {
  title: "Training · FLIH",
  description: "Live connectome model training metrics.",
};

export default function TrainingPage() {
  return <TrainingDashboard />;
}
