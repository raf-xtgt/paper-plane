"use client";
import LeadSearch from "../components/copilot/lead/leadSearch";
import LeadListing from "../components/copilot/lead/leadListing";
import LeadView from "../components/copilot/lead/leadView";
import { useStateController } from "../context/stateController";

export default function CopilotWorkflow() {
  const { isLeadViewOpen } = useStateController();

  return (
    <div className="p-5 h-full bg-gradient-to-br from-gray-50 to-gray-100 overflow-y-auto overflow-x-hidden" >
      <div className="mb-6">
        <LeadSearch></LeadSearch>
      </div>
      <div className="flex flex-col lg:flex-row gap-5 h-[calc(100%-6rem)] relative">
        {/* Main Editor Area */}
        <div className={`transition-all duration-300 ease-in-out bg-white rounded-2xl shadow-lg p-1 border border-gray-200 ${
          isLeadViewOpen ? 'hidden lg:block lg:w-2/5' : 'hidden lg:block lg:w-3/5'
        }`}>
          <LeadListing></LeadListing>
        </div>
        
        {/* Lead View - slides in from right */}
        <div className={`transition-all duration-300 ease-in-out bg-white rounded-2xl shadow-lg p-1 border border-gray-200 ${
          isLeadViewOpen 
            ? 'w-full lg:w-3/5 transform translate-x-0' 
            : 'w-0 lg:w-0 transform translate-x-full overflow-hidden'
        }`}>
          {isLeadViewOpen && <LeadView />}
        </div>
      </div>
    </div>
  );
}