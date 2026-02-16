const { createApp } = Vue;

createApp({
    data() {
        return {
            sidebarOpen: true,
            showSpawn: false,   // Explicitly False
            showSettings: false, // Explicitly False
            loading: false,
            activeAgent: 'Main',
            agents: ['Main'],
            messages: [],
            userInput: '',
            newAgent: { name: '', soul: '', boss: 'Main' },
            settings: { model: 'ollama/gemma3:27b', apiKey: '' }
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
    mounted() {
        console.log("OpenFred Interface Loaded");
        this.loadHistory('Main');
    },
    methods: {
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
            await fetch('/spawn', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(this.newAgent)
            });
            if (!this.agents.includes(this.newAgent.name)) this.agents.push(this.newAgent.name);
            this.newAgent = { name: '', soul: '', boss: 'Main' };
            this.showSpawn = false;
        }
    }
}).mount('#app');