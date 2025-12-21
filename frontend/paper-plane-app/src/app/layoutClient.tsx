"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useStateController } from "./context/stateController";
import { useUser } from "./context/userContext";
import Link from "next/link";
import { FaHome, FaComments, FaUsersCog } from "react-icons/fa";

export default function LayoutClient({ children }: { children: React.ReactNode }) {
  const { navItems, setNavItems } = useStateController();
  const { user } = useUser();
  const router = useRouter();

  // Default navigation setup based on user role
  useEffect(() => {
    const baseNav = [
      { id: "dashboard", label: "About", icon: <FaHome />, route: "/" },
      { id: "chat", label: "Tutorial", icon: <FaComments />, route: "/chat" },
    ];

    if (user?.labels?.includes("admin")) {
      baseNav.push({
        id: "manage-users",
        label: "Manage Users",
        icon: <FaUsersCog />,
        route: "/admin/users",
      });
    }

    setNavItems(baseNav);
  }, [user, setNavItems]);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Bar */}
      <nav className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between shadow-md">
        {/* Clickable title */}
        <div
          className="text-2xl font-bold cursor-pointer hover:text-blue-400 transition-colors"
          onClick={() => router.push("/")}
        >
          Paper Plane
        </div>

        <ul className="flex space-x-6">
          {navItems.map((item) => (
            <li key={item.id}>
              <Link
                href={item.route}
                className="flex items-center space-x-2 hover:text-blue-400 transition-colors"
              >
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>

        <div className="text-sm">{user?.name || "Guest"}</div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
        {children}
      </main>
    </div>
  );
}
