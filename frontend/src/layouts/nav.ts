import {
  Inbox,
  LayoutDashboard,
  Mail,
  Settings,
  Users,
  Megaphone,
  FileText,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
}

export const mainNav: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard },
  { label: "Contacts", to: "/contacts", icon: Users },
  { label: "Campaigns", to: "/campaigns", icon: Megaphone },
  { label: "Templates", to: "/templates", icon: FileText },
  { label: "Email Accounts", to: "/email-accounts", icon: Mail },
  { label: "Inbox", to: "/inbox", icon: Inbox },
  { label: "Settings", to: "/settings", icon: Settings },
];
