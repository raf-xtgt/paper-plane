export const LeadGenService = {

    async triggerLeadGeneration(payload: any): Promise<any> {
      const response = await fetch("http://localhost:8000/api/ppl/agents/lead-gen", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
  
      if (!response.ok) {
        throw new Error("Failed to analyze draft");
      }
  
      return await response.json();
    },
  
  
    async getGeneratedLeadProfiles (): Promise<any>  {
      try {
        const response = await fetch(`http://localhost:8000/api/ppl/lead-profile/listing`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        });
    
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to retrieve sessions');
        }
    
        return await response.json();
      } catch (error) {
        console.error('Error retrieving sessions:', error);
        return { 
          error: error instanceof Error ? error.message : 'Failed to retrieve sessions' 
        };
      }
    },
  
  }