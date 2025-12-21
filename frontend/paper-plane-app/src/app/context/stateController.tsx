"use client";
import { createContext, useContext, useState, ReactNode, useEffect } from 'react';
import { CitationModel } from '../models/citation';
import { PPLPartnerProfile } from '../models/partnerLeadProfile';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  route: string;
}

interface StateControllerState {
  navItems: NavItem[];
  setNavItems: (items: NavItem[]) => void;
  selectedLead: PPLPartnerProfile | null;
  setSelectedLead: (lead: PPLPartnerProfile | null) => void;
  isLeadViewOpen: boolean;
  setIsLeadViewOpen: (isOpen: boolean) => void;
}

const StateControllerContext = createContext<StateControllerState | undefined>(undefined);

export const StateControllerProvider = ({ children }: { children: ReactNode }) => {
  const [navItems, setNavItems] = useState<NavItem[]>([]);
  const [selectedLead, setSelectedLead] = useState<PPLPartnerProfile | null>(null);
  const [isLeadViewOpen, setIsLeadViewOpen] = useState(false);

  return (
    <StateControllerContext.Provider value={{
      navItems,
      setNavItems,
      selectedLead,
      setSelectedLead,
      isLeadViewOpen,
      setIsLeadViewOpen,
    }}>
      {children}
    </StateControllerContext.Provider>
  );
};

export const useStateController = () => {
  const context = useContext(StateControllerContext);
  if (context === undefined) {
    throw new Error('useStateController must be used within a StateControllerProvider');
  }
  return context;
};
