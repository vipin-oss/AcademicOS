"use client";

/**
 * WelcomeModal — shown on first visit to guide new professors.
 * 
 * Dismissible, persists dismissal in localStorage.
 */

import { useState, useEffect } from "react";
import { X, Upload, FileText, Search, Download, CheckCircle2, ArrowRight } from "lucide-react";
import Link from "next/link";

const STORAGE_KEY = "academicos-welcome-dismissed";

export function WelcomeModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const dismissed = localStorage.getItem(STORAGE_KEY);
      if (!dismissed) setOpen(true);
    } catch {
      // localStorage not available
    }
  }, []);

  // Handle Escape key
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        dismiss();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // ignore
    }
    setOpen(false);
  };

  if (!open) return null;

  const steps = [
    {
      icon: Upload,
      title: "Upload Documents",
      description: "Drag and drop certificates, papers, and notices. AI extracts the details automatically.",
      href: "/documents",
      color: "text-blue-600 bg-blue-50",
    },
    {
      icon: CheckCircle2,
      title: "Review & Confirm",
      description: "Check the extracted information and confirm with one click. Edit anything that needs correction.",
      href: "/documents",
      color: "text-emerald-600 bg-emerald-50",
    },
    {
      icon: Search,
      title: "Search & Organize",
      description: "Find anything instantly. Filter by type, year, or keyword across all your records.",
      href: "/search",
      color: "text-amber-600 bg-amber-50",
    },
    {
      icon: Download,
      title: "Generate Reports",
      description: "Export your Academic CV, annual reports, and data in PDF, Excel, or CSV format.",
      href: "/reports",
      color: "text-purple-600 bg-purple-50",
    },
  ];

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" 
      onClick={(e) => { if (e.target === e.currentTarget) dismiss(); }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-modal-title"
    >
      <div className="w-full max-w-lg rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-6 py-5">
          <div>
            <h2 id="welcome-modal-title" className="text-xl font-bold text-[var(--text-primary)]">Welcome to AcademicOS</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Your complete academic record management system
            </p>
          </div>
          <button type="button" onClick={dismiss} className="rounded-lg p-1 hover:bg-[var(--bg-hover)]">
            <X className="h-5 w-5 text-[var(--text-tertiary)]" />
          </button>
        </div>

        {/* Steps */}
        <div className="space-y-4 px-6 py-5">
          <p className="text-sm text-[var(--text-secondary)]">
            AcademicOS helps you manage your entire academic portfolio in 4 simple steps:
          </p>

          <div className="space-y-3">
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <Link
                  key={step.title}
                  href={step.href}
                  onClick={dismiss}
                  className="flex items-start gap-3 rounded-lg border border-[var(--border-subtle)] p-3 transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]"
                >
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${step.color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {i + 1}. {step.title}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                      {step.description}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                </Link>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[var(--border-subtle)] px-6 py-4">
          <p className="text-xs text-[var(--text-tertiary)]">
            Tip: Press <kbd className="rounded border border-[var(--border-subtle)] px-1 py-0.5 text-[10px]">⌘K</kbd> to search anything
          </p>
          <button
            type="button"
            onClick={dismiss}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}
