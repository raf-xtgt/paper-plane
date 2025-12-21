"use client";

import { useRouter } from "next/navigation";
import { useUser } from "../../context/userContext";
import Tutorial from "./tutorial";
import UseCase from "./useCase";
import Footer from "./footer";

export default function Home() {
  const router = useRouter();
  const { user, setUser } = useUser();

  const generateUsername = () => {
    // Generate a random GUID
    const guid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
    
    // Take first 5 characters of the GUID and append to 'user-'
    const shortGuid = guid.replace(/-/g, '').substring(0, 5);
    return `user-${shortGuid}`;
  };

  const handleGetStarted = () => {
    // Check if user_guid exists in localStorage
    const storedUserGuid = localStorage.getItem("user_guid");
    
    if (!storedUserGuid) {
      // Generate a new user GUID
      const newGuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
      
      // Generate a random username with first 5 characters of guid
      const randomUsername = generateUsername();
      
      // Store the GUID and username in localStorage
      localStorage.setItem("user_guid", newGuid);
      localStorage.setItem("user_name", randomUsername);
      
      // Update user context with the username
      setUser({ name: randomUsername, guid: newGuid });
    } else {
      // If user_guid exists, check if user context is already set
      if (!user) {
        // Retrieve the username from localStorage
        const storedUsername = localStorage.getItem("user_name");
        if (storedUsername) {
          setUser({ name: storedUsername, guid: storedUserGuid });
        } else {
          // Generate a username based on the existing guid
          const shortGuid = storedUserGuid.replace(/-/g, '').substring(0, 5);
          const username = `user-${shortGuid}`;
          localStorage.setItem("user_name", username);
          setUser({ name: username, guid: storedUserGuid });
        }
      }
    }
    
    // Redirect to copilotWorkflow page
    router.push("/copilotWorkflow");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Hero Section */}
        <section className="text-center mb-16 mt-8">
          <h1 className="text-4xl md:text-6xl font-bold text-gray-800 mb-6">
            <span className="text-blue-600">Supercharge</span> your business with innovative customer relationship management
          </h1>
          <div className="text-center mt-10">
            <button 
              onClick={handleGetStarted}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-full transition-colors"
            >
              Get Started
            </button>
          </div>
        </section>
        {/* Use Cases Section */}
        <section className="mb-16">
          <UseCase />
        </section>

        {/* Tutorial Section */}
        <section className="mb-16">
          <Tutorial />
        </section>
      </div>
        {/* Footer */}
        <Footer />
    </div>
  );
}