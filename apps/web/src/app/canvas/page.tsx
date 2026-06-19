"use client";

import { Background, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

// Phase 0: an empty React Flow surface to prove the canvas mounts. The node palette,
// Agent config, and compile/run wiring land in Phase 2.
export default function CanvasPage() {
  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-sm font-medium">Agent Canvas</span>
        <Link
          href="/dashboard"
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          ← Dashboard
        </Link>
      </header>
      <div className="flex-1" data-testid="canvas">
        <ReactFlow nodes={[]} edges={[]} fitView>
          <Background />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}
