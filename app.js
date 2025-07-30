const { CloudAdapter, ConfigurationBotFrameworkAuthentication, MemoryStorage, UserState, ActivityHandler } = require('botbuilder');
const restify = require('restify');
const dotenv = require('dotenv');
const jwt = require('jsonwebtoken');
dotenv.config();

// 從環境變數取資料
const MicrosoftAppId = process.env.MicrosoftAppId;
const MicrosoftAppPassword = process.env.MicrosoftAppPassword;
const MicrosoftTenantId = process.env.MicrosoftTenantId;
const PORT = process.env.PORT || 3978;

// 建立 CloudAdapter
const botFrameworkAuthentication = new ConfigurationBotFrameworkAuthentication({
    MicrosoftAppId: MicrosoftAppId,
    MicrosoftAppPassword: MicrosoftAppPassword,
    MicrosoftAppTenantId: MicrosoftTenantId,
    MicrosoftAppType: 'SingleTenant', // *依照多租或單租選填*
});
const adapter = new CloudAdapter(botFrameworkAuthentication);

// 全局錯誤處理
adapter.onTurnError = async (context, error) => {
    console.error(`\n [onTurnError] 未處理的錯誤: ${error.message}\n${error.stack}`);
    try {
        await context.sendActivity(`發生錯誤: ${error.message}`);
    } catch (err) {
        console.error("回應錯誤時發生問題:", err);
    }
};

// 自定義 Teams Bot
class TeamsBot extends ActivityHandler {
    constructor() {
        super();

        // 處理訊息事件
        this.onMessage(async (context, next) => {
            const userMessage = context.activity.text;
            await context.sendActivity(`您剛才說的是: "${userMessage}"`);
            await next();
        });

        // 處理成員加入事件
        this.onMembersAdded(async (context, next) => {
            const membersAdded = context.activity.membersAdded;
            for (let member of membersAdded) {
                if (member.id !== context.activity.recipient.id) {
                    await context.sendActivity('歡迎加入 Teams Bot！');
                    break;
                }
            }
            await next();
        });
    }
}

// 建立機器人實例
const bot = new TeamsBot();

// 建立伺服器
const server = restify.createServer();
server.use(restify.plugins.bodyParser());

// 配置伺服器的訊息端點for Teamsbot串接
server.post('/api/messages', async (req, res) => {
    await adapter.process(req, res, async (context) => {
        const tenantId = context.activity.channelData?.tenant?.id;
        console.log("收到的租戶 ID：", tenantId);
        await bot.run(context);
    });
});

server.listen(PORT, () => {
    const baseUrl = process.env.WebAppHostName
        ? `https://${process.env.WebAppHostName}`
        : `http://localhost:${PORT}`;
    console.log(`伺服器啟動中，網址為 ${baseUrl}`);
});