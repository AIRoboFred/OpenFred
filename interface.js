const { createApp } = Vue;

createApp({
    data() {
        return {
            sidebarOpen: true,
            showSpawn: false,    // Force closed
            showSettings: false, // Force closed
            loading: false,
            activeAgent: 'Main',
            agents: ['Main'],
            messages: [],
            userInput: '',
            newAgent: { name: '', soul: '', boss: 'Main' },
            settings: { 
                model: 'ollama/gemma3:4b', 
                apiKey: '' 
            }
        }
    },
    directives: {
        'auto-resize': {
            updated(el) {
                el.style.height = 'auto';
                el.style.height = el.scrollHeight + 'px';
            }
        }
    },
    async mounted() {
        // Explicitly reset dialog states on mount
        this.showSpawn = false;
        this.showSettings = false;
        
        console.log("OpenFred initialized. Discovering agents...");
        await this.refreshAgents();
        await this.loadHistory(this.activeAgent);
    },
    methods: {
        async refreshAgents() {
            try {
                const res = await fetch('/agents');
                if (res.ok) {
                    this.agents = await res.json();
                }
            } catch (e) {
                console.error("Discovery failed", e);
            }
        },
        async loadHistory(name) {
            this.activeAgent = name;
            this.loading = true;
            try {
                const res = await fetch(`/history?name=${encodeURIComponent(name)}`);
                this.messages = res.ok ? await res.json() : [];
            } catch (e) {
                this.messages = [];
            } finally {
                this.loading = false;
            }
        },
        async sendMessage() {
            if(!this.userInput.trim() || this.loading) return;
            const text = this.userInput;
            this.messages.push({ role: 'user', text });
            this.userInput = '';
            this.loading = true;
            try {
                const url = `/chat?name=${encodeURIComponent(this.activeAgent)}&message=${encodeURIComponent(text)}&model=${this.settings.model}&api_key=${this.settings.apiKey}`;
                const res = await fetch(url, { method: 'POST' });
                const data = await res.json();
                this.messages.push({ role: 'assistant', text: data.reply });
            } catch (e) {
                this.messages.push({ role: 'assistant', text: "❌ Connection Lost." });
            } finally {
                this.loading = false;
            }
        },
        async spawnAgent() {
            if(!this.newAgent.name) return;
            try {
                const res = await fetch('/spawn', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(this.newAgent)
                });
                if (res.ok) {
                    await this.refreshAgents();
                    this.newAgent = { name: '', soul: '', boss: 'Main' };
                    this.showSpawn = false; // Close the dialog
                }
            } catch (e) {
                alert("Spawn failed.");
            }
        }
    }
}).mount('#app');