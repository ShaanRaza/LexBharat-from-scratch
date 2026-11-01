"use client";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Sidebar, type SidebarItem } from "./Sidebar";

// A section of the site with its own menu (Account, Admin, Help): a 240px sidebar on a desktop
// and a sheet behind a Menu button on a phone (docs/DESIGN-DIRECTION.md section 5). The
// same Sidebar component serves both; this file only decides where it sits.
export function AreaLayout({ title, items, children }: { title: string; items: SidebarItem[]; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const path = usePathname();
  return (
    <div className="md:flex md:items-start md:gap-section">
      <div className="hidden md:block">
        <Sidebar title={title} items={items} current={path} />
      </div>
      <div className="mb-4 md:hidden">
        <Button variant="secondary" onClick={() => setOpen(true)} aria-haspopup="dialog">
          {title} menu
        </Button>
        {open && (
          <Dialog title={title} placement="sheet" onClose={() => setOpen(false)}>
            <div onClick={() => setOpen(false)}>
              <Sidebar title={title} items={items} current={path} />
            </div>
          </Dialog>
        )}
      </div>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
