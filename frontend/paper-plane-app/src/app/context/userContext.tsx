"use client";

import { createContext, useContext, useState, useEffect } from "react";

type UserContextType = {
  user: any;
  setUser: (user: any) => void;
};

const UserContext = createContext<UserContextType>({
  user: null,
  setUser: () => {},
});

export const UserProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    // Initialize user from localStorage on component mount
    const storedUserGuid = localStorage.getItem("user_guid");
    if (storedUserGuid) {
      const storedUsername = localStorage.getItem("user_name");
      if (storedUsername) {
        setUser({ name: storedUsername, guid: storedUserGuid });
      } else {
        // Generate username based on existing guid
        const shortGuid = storedUserGuid.replace(/-/g, '').substring(0, 5);
        const username = `user-${shortGuid}`;
        localStorage.setItem("user_name", username);
        setUser({ name: username, guid: storedUserGuid });
      }
    }
  }, []);

  return (
    <UserContext.Provider value={{ user, setUser }}>
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => useContext(UserContext);